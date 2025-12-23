from django.contrib import admin, messages
from django.shortcuts import redirect
from django.urls import path
from django.forms import widgets
import json
from .models import Wallet, PaymentGateway, Transaction, Bank
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
    list_display = ('reference', 'wallet', 'transaction_type', 'amount', 'status', 'created_at')
    list_filter = ('transaction_type', 'status', 'created_at')
    search_fields = ('reference', 'external_reference', 'wallet__user__username')
    readonly_fields = ('reference', 'created_at', 'updated_at')
