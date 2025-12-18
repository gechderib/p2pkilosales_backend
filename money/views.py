from rest_framework import views, viewsets, status, permissions
from drf_spectacular.utils import extend_schema
from rest_framework.response import Response
from django.conf import settings
from .models import PaymentGateway, Transaction, Wallet
from .services import ChapaService
from .serializers import PaymentGatewaySerializer, DepositSerializer
import hmac
import hashlib
import json

@extend_schema(tags=['Money'])
class PaymentGatewayViewSet(viewsets.ModelViewSet):
    queryset = PaymentGateway.objects.all()
    serializer_class = PaymentGatewaySerializer
    permission_classes = [permissions.IsAdminUser] # Only admin can manage gateways

@extend_schema(tags=['Money'], description="Initiate a deposit via Chapa")
class DepositView(views.APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        serializer = DepositSerializer(data=request.data)
        if serializer.is_valid():
            amount = serializer.validated_data['amount']
            user = request.user
            
            try:
                chapa_service = ChapaService()
                checkout_url, transaction = chapa_service.initialize_transaction(
                    user=user,
                    amount=amount,
                    email=user.email,
                    first_name=user.first_name,
                    last_name=user.last_name
                )
                return Response({'checkout_url': checkout_url, 'tx_ref': transaction.reference}, status=status.HTTP_200_OK)
            except Exception as e:
                return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

@extend_schema(tags=['Money'], description="Webhook for Chapa payment notifications", exclude=True)
class ChapaWebhookView(views.APIView):
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        # Verify webhook signature if Chapa sends one (recommended)
        # For now, we'll rely on the secret hash in headers if provided by Chapa
        
        # In a real scenario, you should verify the signature using CHAPA_WEBHOOK_SECRET
        # signature = request.headers.get('Chapa-Signature')
        # ... verification logic ...

        data = request.data
        tx_ref = data.get('tx_ref')
        
        if tx_ref:
            try:
                chapa_service = ChapaService()
                success, message = chapa_service.verify_transaction(tx_ref)
                if success:
                    return Response({'status': 'success'}, status=status.HTTP_200_OK)
                else:
                    return Response({'status': 'failed', 'message': message}, status=status.HTTP_400_BAD_REQUEST)
            except Exception as e:
                return Response({'status': 'error', 'message': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        
        return Response({'status': 'ignored'}, status=status.HTTP_200_OK)
