from celery import shared_task
from .services import ChapaService
import logging

logger = logging.getLogger(__name__)

@shared_task
def sync_chapa_banks():
    try:
        service = ChapaService()
        success, message = service.sync_banks()
        if success:
            logger.info(f"Successfully synced Chapa banks: {message}")
        else:
            logger.error(f"Failed to sync Chapa banks: {message}")
    except Exception as e:
        logger.error(f"Error syncing Chapa banks: {str(e)}")
from .models import Transaction

@shared_task
def verify_pending_transfers():
    """
    Periodically check pending transactions (deposits and withdrawals)
    """
    pending_transactions = Transaction.objects.filter(status=Transaction.Status.PENDING)
    service = ChapaService()
    
    for tx in pending_transactions:
        try:
            if tx.transaction_type == Transaction.TransactionType.DEPOSIT:
                service.verify_transaction(tx.reference)
            elif tx.transaction_type == Transaction.TransactionType.WITHDRAWAL:
                service.verify_transfer(tx.reference)
        except Exception as e:
            logger.error(f"Error verifying transaction {tx.reference}: {str(e)}")
