from django.contrib import admin, messages
from django.shortcuts import redirect
from django.urls import path
from .models import Wallet, PaymentGateway, Transaction, Bank
from .services import ChapaService

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

@admin.register(Transaction)
class TransactionAdmin(admin.ModelAdmin):
    list_display = ('reference', 'wallet', 'transaction_type', 'amount', 'status', 'created_at')
    list_filter = ('transaction_type', 'status', 'created_at')
    search_fields = ('reference', 'external_reference', 'wallet__user__username')
    readonly_fields = ('reference', 'created_at', 'updated_at')
