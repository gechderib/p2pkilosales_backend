"""
Wallet Service for handling all money-related operations.
This service manages wallet balance checks, fee deductions, payment locks, and transfers.
"""
from django.db import transaction
from django.core.exceptions import ValidationError
from decimal import Decimal
from .models import Wallet, Transaction, PlatformConfig
import uuid


class InsufficientBalanceError(Exception):
    """Raised when wallet has insufficient balance."""
    pass


class WalletService:
    """
    Service class for wallet operations.
    All methods use atomic transactions to ensure data consistency.
    """
    
    @staticmethod
    def get_config():
        """Get platform configuration."""
        return PlatformConfig.get_config()
    
    @staticmethod
    def check_balance_for_listing(user):
        """
        Check if user has sufficient balance to create a travel listing.
        
        Args:
            user: User instance
            
        Returns:
            bool: True if user has sufficient balance
        """
        config = WalletService.get_config()
        wallet = user.wallet
        return wallet.balance >= config.min_balance_for_travel_listing
    
    @staticmethod
    def check_balance_for_request(user, total_amount):
        """
        Check if user has sufficient balance to create a package request.
        User needs: min_balance + total_price (which will be locked)
        
        Args:
            user: User instance
            total_amount: Total price of the package request
            
        Returns:
            bool: True if user has sufficient balance
        """
        config = WalletService.get_config()
        wallet = user.wallet
        required_balance = config.min_balance_for_package_request + Decimal(total_amount)
        return wallet.balance >= required_balance
    
    @staticmethod
    @transaction.atomic
    def deduct_listing_fee(user, listing):
        """
        Deduct the listing creation fee from user's wallet.
        This fee goes to system revenue.
        
        Args:
            user: User instance
            listing: TravelListing instance
            
        Returns:
            Transaction: Created transaction record
            
        Raises:
            InsufficientBalanceError: If wallet has insufficient balance
        """
        config = WalletService.get_config()
        wallet = user.wallet
        fee_amount = config.min_balance_for_travel_listing
        
        # Check balance
        if wallet.balance < fee_amount:
            raise InsufficientBalanceError(
                f"Insufficient balance. Required: {fee_amount}, Available: {wallet.balance}"
            )
        
        # Deduct from wallet
        wallet.balance -= fee_amount
        wallet.save()
        
        # Create transaction record
        txn = Transaction.objects.create(
            wallet=wallet,
            amount=fee_amount,
            transaction_type=Transaction.TransactionType.LISTING_FEE,
            status=Transaction.Status.SUCCESS,
            reference=f"listing-fee-{uuid.uuid4().hex[:16]}",
            description=f"Fee for creating travel listing #{listing.id}",
            transaction_category=Transaction.TransactionCategory.SYSTEM_REVENUE,
            related_listing=listing
        )
        
        return txn
    
    @staticmethod
    @transaction.atomic
    def deduct_request_fee_and_lock_amount(user, package_request):
        """
        Deduct the request creation fee and lock the total price.
        Fee goes to system revenue, locked amount stays in user's wallet.
        
        Args:
            user: User instance
            package_request: PackageRequest instance
            
        Returns:
            tuple: (fee_transaction, lock_transaction)
            
        Raises:
            InsufficientBalanceError: If wallet has insufficient balance
        """
        config = WalletService.get_config()
        wallet = user.wallet
        fee_amount = config.min_balance_for_package_request
        lock_amount = package_request.total_price
        total_required = fee_amount + lock_amount
        
        # Check balance
        if wallet.balance < total_required:
            raise InsufficientBalanceError(
                f"Insufficient balance. Required: {total_required}, Available: {wallet.balance}"
            )
        
        # Deduct fee from balance
        wallet.balance -= fee_amount
        
        # Lock the payment amount
        wallet.balance -= lock_amount
        wallet.locked_balance += lock_amount
        wallet.save()
        
        # Create fee transaction
        fee_txn = Transaction.objects.create(
            wallet=wallet,
            amount=fee_amount,
            transaction_type=Transaction.TransactionType.REQUEST_FEE,
            status=Transaction.Status.SUCCESS,
            reference=f"request-fee-{uuid.uuid4().hex[:16]}",
            description=f"Fee for creating package request #{package_request.id}",
            transaction_category=Transaction.TransactionCategory.SYSTEM_REVENUE,
            related_package_request=package_request
        )
        
        # Create lock transaction
        lock_txn = Transaction.objects.create(
            wallet=wallet,
            amount=lock_amount,
            transaction_type=Transaction.TransactionType.PAYMENT_LOCK,
            status=Transaction.Status.SUCCESS,
            reference=f"lock-{uuid.uuid4().hex[:16]}",
            description=f"Locked payment for package request #{package_request.id}",
            transaction_category=Transaction.TransactionCategory.USER_TRANSACTION,
            related_package_request=package_request
        )
        
        return fee_txn, lock_txn
    
    @staticmethod
    @transaction.atomic
    def release_payment_to_traveler(package_request):
        """
        Release locked payment to traveler when package is completed.
        Deducts platform commission from the payment.
        
        Args:
            package_request: PackageRequest instance
            
        Returns:
            tuple: (payment_transaction, commission_transaction)
        """
        config = WalletService.get_config()
        requester_wallet = package_request.user.wallet
        traveler_wallet = package_request.travel_listing.user.wallet
        
        locked_amount = package_request.total_price
        commission_percentage = config.platform_commission_percentage / Decimal('100')
        commission_amount = locked_amount * commission_percentage
        traveler_amount = locked_amount - commission_amount
        
        # Unlock from requester
        requester_wallet.locked_balance -= locked_amount
        requester_wallet.save()
        
        # Transfer to traveler
        traveler_wallet.balance += traveler_amount
        traveler_wallet.save()
        
        # Create payment release transaction
        payment_txn = Transaction.objects.create(
            wallet=requester_wallet,
            amount=traveler_amount,
            transaction_type=Transaction.TransactionType.PAYMENT_RELEASE,
            status=Transaction.Status.SUCCESS,
            reference=f"release-{uuid.uuid4().hex[:16]}",
            description=f"Payment released to traveler for package request #{package_request.id}",
            transaction_category=Transaction.TransactionCategory.INTERNAL_TRANSFER,
            recipient_wallet=traveler_wallet,
            related_package_request=package_request
        )
        
        # Create commission transaction
        commission_txn = Transaction.objects.create(
            wallet=requester_wallet,
            amount=commission_amount,
            transaction_type=Transaction.TransactionType.COMMISSION,
            status=Transaction.Status.SUCCESS,
            reference=f"commission-{uuid.uuid4().hex[:16]}",
            description=f"Platform commission for package request #{package_request.id}",
            transaction_category=Transaction.TransactionCategory.SYSTEM_REVENUE,
            related_package_request=package_request
        )
        
        return payment_txn, commission_txn
    
    @staticmethod
    @transaction.atomic
    def refund_locked_amount(package_request):
        """
        Refund locked amount back to user when request is rejected/cancelled.
        
        Args:
            package_request: PackageRequest instance
            
        Returns:
            Transaction: Created transaction record
        """
        wallet = package_request.user.wallet
        locked_amount = package_request.total_price
        
        # Unlock amount
        wallet.locked_balance -= locked_amount
        wallet.balance += locked_amount
        wallet.save()
        
        # Create unlock transaction
        txn = Transaction.objects.create(
            wallet=wallet,
            amount=locked_amount,
            transaction_type=Transaction.TransactionType.PAYMENT_UNLOCK,
            status=Transaction.Status.SUCCESS,
            reference=f"unlock-{uuid.uuid4().hex[:16]}",
            description=f"Refund for rejected/cancelled package request #{package_request.id}",
            transaction_category=Transaction.TransactionCategory.USER_TRANSACTION,
            related_package_request=package_request
        )
        
        return txn
