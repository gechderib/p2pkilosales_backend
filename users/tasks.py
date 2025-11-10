from celery import shared_task
from django.contrib.auth import get_user_model
from .utils import send_verification_email

User = get_user_model()

@shared_task
def send_verification_email_task(user_id, otp_code):
    """
    Run send_verification_email asynchronously.
    """
    try:
        user = User.objects.get(id=user_id)
        send_verification_email(user, otp_code)
        return f"Verification email sent to {user.email}"
    except Exception as e:
        return f"Failed to send verification email: {str(e)}"


@shared_task
def send_report():
    print("Sending daily report...")
