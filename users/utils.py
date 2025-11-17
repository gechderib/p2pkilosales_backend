# from django.core.mail import send_mail
# from django.template.loader import render_to_string
# from django.conf import settings
# from django.utils.html import strip_tags
# import logging

# logger = logging.getLogger(__name__)

# def send_verification_email(user, otp_code):
#     """
#     Send verification email with OTP code
#     """
#     subject = 'Verify Your Email - P2P Kilosales'
    
#     try:
#         # Render the HTML template
#         html_message = render_to_string('email_verification.html', {
#             'user': user,
#             'otp_code': otp_code
#         })
        
#         # Create plain text version
#         plain_message = strip_tags(html_message)
        
#         print(f"\nAttempting to send verification email to {user.email}")
#         print(f"Email content: {plain_message}")
        
#         # Send email
#         send_mail(
#             subject=subject,
#             message=plain_message,
#             from_email=settings.EMAIL_HOST_USER,
#             recipient_list=[user.email],
#             html_message=html_message,
#             fail_silently=False,
#         )
#         print(f"Verification email sent successfully to {user.email}")
#     except Exception as e:
#         print(f"Failed to send verification email to {user.email}: {str(e)}")
#         raise 

from django.contrib.auth import get_user_model
from django.template.loader import render_to_string
from django.utils.html import strip_tags
from django.conf import settings

import logging

from .gmail_utils import send_message 
User = get_user_model()

logger = logging.getLogger(__name__)

def send_verification_email(user, otp_code):
    """
    Send verification email with OTP code using Gmail API
    """
    subject = 'Verify Your Email - P2P Kilosales'
    
    try:
        # Render the HTML template
        html_message = render_to_string('email_verification.html', {
            'user': user,
            'otp_code': otp_code
        })
        
        # Plain text fallback
        plain_message = strip_tags(html_message)
        
        print(f"\nAttempting to send verification email to {user.email}")
        print(f"Email content: {plain_message}")
        
        # Send via Gmail API
        # The sender must match the authorized Gmail account used in token.json
        sender_email = settings.EMAIL_HOST_USER
        send_message(
            sender=sender_email,
            to=user.email,
            subject=subject,
            plain_text=plain_message,
            html_text=html_message
        )
        
        print(f"Verification email sent successfully to {user.email}")
    except Exception as e:
        print(f"Failed to send verification email to {user.email}: {str(e)}")
        raise

