from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    PaymentGatewayViewSet, DepositView, ChapaWebhookView, 
    VerifyTransactionView, WalletBalanceView, WithdrawalView, 
    BanksListView, TransferApprovalView, VerifyTransferView, VerifyPendingTransfersView,
    UserTransactionViewSet
)

router = DefaultRouter()
router.register(r'gateways', PaymentGatewayViewSet)
router.register(r'transactions', UserTransactionViewSet, basename='user-transactions')

urlpatterns = [
    path('', include(router.urls)),
    path('balance/', WalletBalanceView.as_view(), name='wallet-balance'),
    path('banks/', BanksListView.as_view(), name='banks-list'),
    path('deposit/', DepositView.as_view(), name='deposit'),
    
    path('withdrawal/', WithdrawalView.as_view(), name='withdrawal'),
    path('verify/<str:tx_ref>/', VerifyTransactionView.as_view(), name='verify-transaction'),
    path('verify-transfer/<str:tx_ref>/', VerifyTransferView.as_view(), name='verify-transfer'),

    path('webhook/chapa/', ChapaWebhookView.as_view(), name='chapa-webhook'),
    path('webhook/chapa/transfer-approval/', TransferApprovalView.as_view(), name='chapa-transfer-approval'),
    path('verify-pending-transfers/', VerifyPendingTransfersView.as_view(), name='verify-pending-transfers'),
]



