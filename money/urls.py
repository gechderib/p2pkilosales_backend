from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import PaymentGatewayViewSet, DepositView, ChapaWebhookView

router = DefaultRouter()
router.register(r'gateways', PaymentGatewayViewSet)

urlpatterns = [
    path('', include(router.urls)),
    path('deposit/', DepositView.as_view(), name='deposit'),
    path('webhook/chapa/', ChapaWebhookView.as_view(), name='chapa-webhook'),
]
