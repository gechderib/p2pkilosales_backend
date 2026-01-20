from django.db import models
from django.conf import settings
from django.utils.translation import gettext_lazy as _
import uuid

class Wallet(models.Model):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='wallet')
    balance = models.DecimalField(max_digits=12, decimal_places=2, default=0.00)
    locked_balance = models.DecimalField(max_digits=12, decimal_places=2, default=0.00)
    currency = models.CharField(max_length=3, default='ETB')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.user.username}'s Wallet ({self.balance} {self.currency})"

class PaymentGateway(models.Model):
    name = models.CharField(max_length=50, unique=True)
    code = models.SlugField(max_length=50, unique=True)
    is_active = models.BooleanField(default=False)
    config = models.JSONField(default=dict, blank=True, help_text="Configuration for the payment gateway (API keys, etc.)")
    required_fields = models.JSONField(default=list, blank=True, help_text="List of required configuration fields")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.name

class Transaction(models.Model):
    class TransactionType(models.TextChoices):
        DEPOSIT = 'DEPOSIT', _('Deposit')
        WITHDRAWAL = 'WITHDRAWAL', _('Withdrawal')
        LISTING_FEE = 'LISTING_FEE', _('Travel Listing Fee')
        REQUEST_FEE = 'REQUEST_FEE', _('Package Request Fee')
        PAYMENT_LOCK = 'PAYMENT_LOCK', _('Payment Lock')
        PAYMENT_UNLOCK = 'PAYMENT_UNLOCK', _('Payment Unlock')
        PAYMENT_RELEASE = 'PAYMENT_RELEASE', _('Payment Release')
        COMMISSION = 'COMMISSION', _('Platform Commission')

    class Status(models.TextChoices):
        PENDING = 'PENDING', _('Pending')
        SUCCESS = 'SUCCESS', _('Success')
        FAILED = 'FAILED', _('Failed')
    
    class TransactionCategory(models.TextChoices):
        USER_TRANSACTION = 'USER_TRANSACTION', _('User Transaction')
        SYSTEM_REVENUE = 'SYSTEM_REVENUE', _('System Revenue')
        INTERNAL_TRANSFER = 'INTERNAL_TRANSFER', _('Internal Transfer')

    wallet = models.ForeignKey(Wallet, on_delete=models.CASCADE, related_name='transactions')
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    transaction_type = models.CharField(max_length=20, choices=TransactionType.choices)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING)
    reference = models.CharField(max_length=100, unique=True, default=uuid.uuid4)
    external_reference = models.CharField(max_length=100, blank=True, null=True)
    gateway = models.ForeignKey(PaymentGateway, on_delete=models.SET_NULL, null=True, blank=True)
    description = models.TextField(blank=True)
    
    # Ledger-based fields
    transaction_category = models.CharField(
        max_length=20, 
        choices=TransactionCategory.choices, 
        default=TransactionCategory.USER_TRANSACTION,
        help_text="Category for ledger tracking"
    )
    recipient_wallet = models.ForeignKey(
        Wallet, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True,
        related_name='received_transactions',
        help_text="Recipient wallet for transfers"
    )
    
    # Relationship fields for tracking
    related_listing = models.ForeignKey(
        'listings.TravelListing',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='transactions'
    )
    related_package_request = models.ForeignKey(
        'listings.PackageRequest',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='transactions'
    )
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.transaction_type} - {self.amount} - {self.status}"

class Bank(models.Model):
    gateway = models.ForeignKey(PaymentGateway, on_delete=models.CASCADE, related_name='banks')
    name = models.CharField(max_length=100)
    code = models.CharField(max_length=50)
    slug = models.SlugField(max_length=100, blank=True, null=True)
    swift = models.CharField(max_length=50, blank=True, null=True)
    acct_length = models.IntegerField(blank=True, null=True)
    is_active = models.BooleanField(default=True)
    is_mobilemoney = models.BooleanField(default=False)
    currency = models.CharField(max_length=3, default='ETB')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ('gateway', 'code')

    def __str__(self):
        return f"{self.name} ({self.gateway.name})"

class PlatformConfig(models.Model):
    """
    Singleton model for platform-wide money configuration.
    Only one instance should exist.
    """
    # Travel Listing Requirements
    min_balance_for_travel_listing = models.DecimalField(
        max_digits=10, 
        decimal_places=2, 
        default=10.00,
        help_text="Minimum wallet balance required to create a travel listing"
    )
    
    # Package Request Requirements
    min_balance_for_package_request = models.DecimalField(
        max_digits=10, 
        decimal_places=2, 
        default=10.00,
        help_text="Minimum wallet balance required to create a package request"
    )
    
    # Platform Fees
    platform_commission_percentage = models.DecimalField(
        max_digits=5, 
        decimal_places=2, 
        default=5.00,
        help_text="Percentage commission taken from completed package deliveries"
    )
    
    tax_percentage = models.DecimalField(
        max_digits=5, 
        decimal_places=2, 
        default=15.00,
        help_text="Tax/VAT percentage"
    )
    
    # Deposit Limits
    min_deposit_amount = models.DecimalField(
        max_digits=10, 
        decimal_places=2, 
        default=10.00,
        help_text="Minimum amount for deposits"
    )
    
    max_deposit_amount = models.DecimalField(
        max_digits=10, 
        decimal_places=2, 
        default=10000.00,
        help_text="Maximum amount for deposits"
    )
    
    # Withdrawal Limits
    min_withdrawal_amount = models.DecimalField(
        max_digits=10, 
        decimal_places=2, 
        default=50.00,
        help_text="Minimum amount for withdrawals"
    )
    
    max_withdrawal_amount = models.DecimalField(
        max_digits=10, 
        decimal_places=2, 
        default=5000.00,
        help_text="Maximum amount for withdrawals"
    )
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = "Platform Configuration"
        verbose_name_plural = "Platform Configuration"
    
    def save(self, *args, **kwargs):
        """Enforce singleton pattern - only one config instance allowed."""
        self.pk = 1
        super().save(*args, **kwargs)
    
    def delete(self, *args, **kwargs):
        """Prevent deletion of the config."""
        pass
    
    @classmethod
    def get_config(cls):
        """Get or create the singleton config instance."""
        config, created = cls.objects.get_or_create(pk=1)
        return config
    
    def __str__(self):
        return "Platform Configuration"
