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

    class Status(models.TextChoices):
        PENDING = 'PENDING', _('Pending')
        SUCCESS = 'SUCCESS', _('Success')
        FAILED = 'FAILED', _('Failed')

    wallet = models.ForeignKey(Wallet, on_delete=models.CASCADE, related_name='transactions')
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    transaction_type = models.CharField(max_length=20, choices=TransactionType.choices)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING)
    reference = models.CharField(max_length=100, unique=True, default=uuid.uuid4)
    external_reference = models.CharField(max_length=100, blank=True, null=True)
    gateway = models.ForeignKey(PaymentGateway, on_delete=models.SET_NULL, null=True, blank=True)
    description = models.TextField(blank=True)
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
