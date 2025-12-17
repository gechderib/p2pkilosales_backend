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
            "first_name": first_name,
            "last_name": last_name,
            "tx_ref": tx_ref,
            "callback_url": callback_url or self.config.get('CHAPA_CALLBACK_BASE_URL'),
            "return_url": self.config.get('CHAPA_RETURN_URL'), # Optional return URL
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

    # Placeholder for withdrawal/transfer if Chapa supports it and user has permissions
    def initiate_transfer(self, user, amount, bank_code, account_number, beneficiary_name):
        # Implementation depends on Chapa Transfer API availability
        pass
