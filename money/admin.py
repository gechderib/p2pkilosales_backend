from django.contrib import admin, messages
from django.shortcuts import redirect
from django.urls import path
from django.forms import widgets
import json
from .models import Wallet, PaymentGateway, Transaction, Bank, PlatformConfig
from .services import ChapaService

class PrettyJSONWidget(widgets.Textarea):
    def __init__(self, attrs=None):
        default_attrs = {'rows': '20', 'cols': '80', 'style': 'font-family: monospace;'}
        if attrs:
            default_attrs.update(attrs)
        super().__init__(default_attrs)

    def format_value(self, value):
        if value is None:
            return ""
        
        # If it's a string, it might be double-encoded or just raw string
        if isinstance(value, str):
            try:
                # Try to parse it to a dict/list first
                value = json.loads(value)
            except (ValueError, TypeError):
                # If it's not valid JSON string, just return it as is
                return value
                
        try:
            return json.dumps(value, indent=4, sort_keys=True)
        except (ValueError, TypeError):
            return value

@admin.register(Bank)
class BankAdmin(admin.ModelAdmin):
    list_display = ('name', 'code', 'gateway', 'is_active', 'is_mobilemoney', 'currency')
    list_filter = ('gateway', 'is_active', 'is_mobilemoney')
    search_fields = ('name', 'code')
    
    change_list_template = "admin/money/bank_change_list.html"

    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path('sync-banks/', self.sync_banks, name='sync-banks'),
        ]
        return custom_urls + urls

    def sync_banks(self, request):
        try:
            service = ChapaService()
            success, message = service.sync_banks()
            if success:
                self.message_user(request, message)
            else:
                self.message_user(request, message, level=messages.ERROR)
        except Exception as e:
            self.message_user(request, f"Error: {str(e)}", level=messages.ERROR)
        return redirect("..")

@admin.register(Wallet)
class WalletAdmin(admin.ModelAdmin):
    list_display = ('user', 'balance', 'locked_balance', 'currency', 'updated_at')
    search_fields = ('user__username', 'user__email')
    readonly_fields = ('balance', 'locked_balance') # Prevent manual balance editing without transaction

@admin.register(PaymentGateway)
class PaymentGatewayAdmin(admin.ModelAdmin):
    list_display = ('name', 'code', 'is_active', 'updated_at')
    list_filter = ('is_active',)
    search_fields = ('name', 'code')

    def formfield_for_dbfield(self, db_field, **kwargs):
        if db_field.name in ['config', 'required_fields']:
            kwargs['widget'] = PrettyJSONWidget
        return super().formfield_for_dbfield(db_field, **kwargs)

@admin.register(Transaction)
class TransactionAdmin(admin.ModelAdmin):
    list_display = ('reference', 'wallet', 'transaction_type', 'transaction_category', 'amount', 'status', 'created_at')
    list_filter = ('transaction_type', 'transaction_category', 'status', 'created_at')
    search_fields = ('reference', 'external_reference', 'wallet__user__username', 'description')
    readonly_fields = ('reference', 'created_at', 'updated_at')
    actions = ['verify_transactions']

    @admin.action(description='Verify selected transactions')
    def verify_transactions(self, request, queryset):
        service = ChapaService()
        success_count = 0
        failed_count = 0
        processed_count = 0

        for tx in queryset:
            if tx.status != Transaction.Status.PENDING:
                continue
            
            processed_count += 1
            try:
                success = False
                message = ""
                
                if tx.transaction_type == Transaction.TransactionType.DEPOSIT:
                    success, message = service.verify_transaction(tx.reference)
                elif tx.transaction_type == Transaction.TransactionType.WITHDRAWAL:
                    success, message = service.verify_transfer(tx.reference)
                
                if success:
                    success_count += 1
                else:
                    failed_count += 1
            except Exception as e:
                failed_count += 1
        
        self.message_user(
            request,
            f"Processed {processed_count} transactions. Success: {success_count}, Failed: {failed_count}.",
            level=messages.SUCCESS if failed_count == 0 else messages.WARNING
        )

@admin.register(PlatformConfig)
class PlatformConfigAdmin(admin.ModelAdmin):
    """
    Admin for Platform Configuration (Singleton).
    """
    list_display = [
        'min_balance_for_travel_listing',
        'min_balance_for_package_request',
        'platform_commission_percentage',
        'tax_percentage',
        'updated_at'
    ]
    
    fieldsets = (
        ('Travel & Package Requirements', {
            'fields': ('min_balance_for_travel_listing', 'min_balance_for_package_request')
        }),
        ('Platform Fees', {
            'fields': ('platform_commission_percentage', 'tax_percentage')
        }),
        ('Deposit Limits', {
            'fields': ('min_deposit_amount', 'max_deposit_amount')
        }),
        ('Withdrawal Limits', {
            'fields': ('min_withdrawal_amount', 'max_withdrawal_amount')
        }),
    )
    
    def has_add_permission(self, request):
        """Only allow one instance."""
        return not PlatformConfig.objects.exists()
    
    def has_delete_permission(self, request, obj=None):
        """Prevent deletion."""
        return False
