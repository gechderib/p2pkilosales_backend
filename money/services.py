import requests
from django.conf import settings
from .models import PaymentGateway, Transaction, Wallet
import uuid
import json

class ChapaService:
    def __init__(self):
        self.gateway = PaymentGateway.objects.get(code='chapa', is_active=True)
        self.config = self.gateway.config
        self.base_url = self.config.get('CHAPA_BASE_URL', 'https://api.chapa.co/v1')
        self.headers = {
            'Authorization': f"Bearer {self.config.get('CHAPA_SECRET_KEY')}",
            'Content-Type': 'application/json'
        }

    def verify_webhook_signature(self, body_data, chapa_signature=None, x_chapa_signature=None):
        """
        Verify the webhook signature from Chapa.
        Chapa-Signature: HMAC SHA256 signature of secret key signed using secret key (constant).
        x-chapa-signature: HMAC SHA256 signature of the event payload signed using secret key.
        """
        import hmac
        import hashlib
        
        # Use CHAPA_WEBHOOK_SECRET if available, otherwise fallback to CHAPA_SECRET_KEY
        secret = self.config.get('CHAPA_WEBHOOK_SECRET') or self.config.get('CHAPA_SECRET_KEY')
        if not secret:
            return False

        # 1. Verify x-chapa-signature (Payload signature)
        if x_chapa_signature:
            # Chapa sends JSON body. We need to ensure we use the exact same string representation.
            # Usually, it's the raw body.
            if isinstance(body_data, dict):
                payload = json.dumps(body_data, separators=(',', ':'))
                payload_bytes = payload.encode('utf-8')
            elif isinstance(body_data, str):
                payload = body_data
                payload_bytes = payload.encode('utf-8')
            elif isinstance(body_data, bytes):
                payload_bytes = body_data
            else:
                payload_bytes = str(body_data).encode('utf-8')

            expected_signature = hmac.new(
                secret.encode('utf-8'),
                payload_bytes,
                hashlib.sha256
            ).hexdigest()
            
            if hmac.compare_digest(expected_signature, x_chapa_signature):
                return True

        # 2. Verify chapa-signature (Secret key signature - constant)
        if chapa_signature:
            # "HMAC SHA256 signature of your secret key signed using your secret key"
            expected_chapa_sig = hmac.new(
                secret.encode('utf-8'),
                secret.encode('utf-8'),
                hashlib.sha256
            ).hexdigest()
            
            if hmac.compare_digest(expected_chapa_sig, chapa_signature):
                return True

        return False

    def initialize_transaction(self, user, amount, email, first_name, last_name, callback_url=None):
        tx_ref = f"tx-{uuid.uuid4()}"
        
        # Create pending transaction
        transaction = Transaction.objects.create(
            wallet=user.wallet,
            amount=amount,
            transaction_type=Transaction.TransactionType.DEPOSIT,
            status=Transaction.Status.PENDING,
            reference=tx_ref,
            gateway=self.gateway,
            description="Deposit via Chapa"
        )

        payload = {
            "amount": str(amount),
            "currency": "ETB",
            "email": email,
            "first_name": first_name or user.username,
            "last_name": last_name or "User",
            "tx_ref": tx_ref,
            "callback_url": callback_url or self.config.get('CHAPA_CALLBACK_BASE_URL'),
            "return_url": f"{self.config.get('CHAPA_RETURN_URL', '')}{'&' if '?' in self.config.get('CHAPA_RETURN_URL', '') else '?'}tx_ref={tx_ref}" if self.config.get('CHAPA_RETURN_URL') else None,
            "customization": {
                "title": "Wallet Deposit",
                "description": "Deposit to your wallet"
            }
        }

        try:
            response = requests.post(f"{self.base_url}/transaction/initialize", json=payload, headers=self.headers)
            response.raise_for_status()
            data = response.json()
            if data['status'] == 'success':
                return data['data']['checkout_url'], transaction
            else:
                transaction.status = Transaction.Status.FAILED
                transaction.description = f"Chapa init failed: {data.get('message')}"
                transaction.save()
                raise Exception(f"Chapa initialization failed: {data.get('message')}")
        except requests.exceptions.HTTPError as e:
            error_data = {}
            try:
                error_data = e.response.json()
            except:
                error_data = {'text': e.response.text}
            
            transaction.status = Transaction.Status.FAILED
            transaction.description = f"Chapa init error: {json.dumps(error_data)}"
            transaction.save()
            raise Exception(f"Chapa initialization failed: {json.dumps(error_data)}")
        except Exception as e:
            transaction.status = Transaction.Status.FAILED
            transaction.description = f"Chapa init error: {str(e)}"
            transaction.save()
            raise e

    def verify_transaction(self, tx_ref):
        try:
            response = requests.get(f"{self.base_url}/transaction/verify/{tx_ref}", headers=self.headers)
            response.raise_for_status()
            data = response.json()
            
            transaction = Transaction.objects.get(reference=tx_ref)
            
            if data['status'] == 'success':
                if transaction.status != Transaction.Status.SUCCESS:
                    transaction.status = Transaction.Status.SUCCESS
                    transaction.external_reference = data['data'].get('reference') # Chapa reference
                    transaction.save()
                    
                    # Credit wallet
                    wallet = transaction.wallet
                    wallet.balance += transaction.amount
                    wallet.save()
                    
                return True, "Transaction verified successfully"
            else:
                transaction.status = Transaction.Status.FAILED
                transaction.save()
                return False, "Transaction verification failed"
                
        except Transaction.DoesNotExist:
            return False, "Transaction not found"
        except Exception as e:
            return False, str(e)

    def get_banks(self):
        try:
            response = requests.get(f"{self.base_url}/banks", headers=self.headers)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            raise Exception(f"Failed to fetch banks: {str(e)}")

    def sync_banks(self):
        from .models import Bank
        import logging
        logger = logging.getLogger(__name__)
        
        try:
            data = self.get_banks()
            banks_data = data.get('data', [])
            
            if not banks_data and data.get('status') == 'failed':
                return False, data.get('message', 'Failed to sync banks')

            count = 0
            for bank_info in banks_data:
                Bank.objects.update_or_create(
                    gateway=self.gateway,
                    code=str(bank_info.get('id')),
                    defaults={
                        'name': bank_info.get('name'),
                        'slug': bank_info.get('slug'),
                        'swift': bank_info.get('swift'),
                        'acct_length': bank_info.get('acct_length'),
                        'is_active': bank_info.get('active') == 1 or bank_info.get('is_active') == 1,
                        'is_mobilemoney': bank_info.get('is_mobilemoney') == 1,
                        'currency': bank_info.get('currency', 'ETB'),
                    }
                )
                count += 1
            
            return True, f"Synced {count} banks"
        except Exception as e:
            logger.error(f"Bank sync error: {str(e)}")
            return False, str(e)

    def initiate_transfer(self, user, amount, bank_code, account_number, account_name):
        wallet = user.wallet
        if wallet.balance < amount:
            raise Exception("Insufficient balance")

        tx_ref = f"tr-{uuid.uuid4().hex[:32]}"
        
        # Create pending withdrawal transaction
        transaction = Transaction.objects.create(
            wallet=wallet,
            amount=amount,
            transaction_type=Transaction.TransactionType.WITHDRAWAL,
            status=Transaction.Status.PENDING,
            reference=tx_ref,
            gateway=self.gateway,
            description=f"Withdrawal to {account_name} ({account_number})"
        )

        # Lock balance
        wallet.balance -= amount
        wallet.locked_balance += amount
        wallet.save()

        # Try to convert bank_code to int if it's a numeric string
        try:
            bank_code_int = int(bank_code)
        except (ValueError, TypeError):
            bank_code_int = bank_code

        payload = {
            "account_name": account_name,
            "account_number": account_number,
            "amount": str(amount),
            "currency": "ETB",
            "reference": tx_ref,
            "bank_code": bank_code_int
        }

        try:
            response = requests.post(f"{self.base_url}/transfers", json=payload, headers=self.headers)
            response.raise_for_status()
            data = response.json()
            
            if data['status'] == 'success':
                return data, transaction
            else:
                # Rollback balance if Chapa rejects immediately
                wallet.balance += amount
                wallet.locked_balance -= amount
                wallet.save()
                
                transaction.status = Transaction.Status.FAILED
                transaction.description = f"Chapa transfer failed: {data.get('message')}"
                transaction.save()
                raise Exception(f"Chapa transfer failed: {data.get('message')}")
        except requests.exceptions.HTTPError as e:
            error_data = {}
            try:
                error_data = e.response.json()
            except:
                error_data = {'text': e.response.text}
            
            # Rollback balance
            wallet.balance += amount
            wallet.locked_balance -= amount
            wallet.save()
            
            transaction.status = Transaction.Status.FAILED
            transaction.description = f"Chapa transfer error: {json.dumps(error_data)}"
            transaction.save()
            raise Exception(f"Chapa transfer failed: {json.dumps(error_data)}")
        except Exception as e:
            # Rollback balance on other errors
            wallet.balance += amount
            wallet.locked_balance -= amount
            wallet.save()
            
            transaction.status = Transaction.Status.FAILED
            transaction.description = f"Chapa transfer error: {str(e)}"
            transaction.save()
            raise e

    def verify_transfer(self, tx_ref):
        try:
            response = requests.get(f"{self.base_url}/transfers/verify/{tx_ref}", headers=self.headers)
            response.raise_for_status()
            data = response.json()
            
            transaction = Transaction.objects.get(reference=tx_ref)
            wallet = transaction.wallet
            
            if data['status'] == 'success':
                # Handle Test Mode response: {"message":"Transfer details (Test Mode)","status":"success","data":[null]}
                is_test_mode = self.config.get('IS_TEST_MODE', False)
                transfer_data = data.get('data')
                
                if is_test_mode and (transfer_data == [None] or transfer_data == []):
                    # In test mode, if we get success but null data, assume it's a successful test transfer
                    if transaction.status != Transaction.Status.SUCCESS:
                        transaction.status = Transaction.Status.SUCCESS
                        transaction.description += " (Test Mode Success)"
                        transaction.save()
                        
                        # Finalize withdrawal: remove from locked balance
                        wallet.locked_balance -= transaction.amount
                        wallet.save()
                    return True, "Transfer verified (Test Mode)"

                if isinstance(transfer_data, dict):
                    transfer_status = transfer_data.get('status')
                    if transfer_status == 'success':
                        if transaction.status != Transaction.Status.SUCCESS:
                            transaction.status = Transaction.Status.SUCCESS
                            transaction.external_reference = transfer_data.get('chapa_transfer_id')
                            transaction.save()
                            
                            # Finalize withdrawal: remove from locked balance
                            wallet.locked_balance -= transaction.amount
                            wallet.save()
                    elif transfer_status == 'failed':
                        if transaction.status != Transaction.Status.FAILED:
                            transaction.status = Transaction.Status.FAILED
                            transaction.save()
                            
                            # Rollback withdrawal: return to balance
                            wallet.locked_balance -= transaction.amount
                            wallet.balance += transaction.amount
                            wallet.save()
                    
                    return True, f"Transfer status: {transfer_status}"
                
                return False, "Unexpected transfer data format"
            else:
                return False, "Transfer verification failed"
                
        except Transaction.DoesNotExist:
            return False, "Transaction not found"
        except Exception as e:
            return False, str(e)
