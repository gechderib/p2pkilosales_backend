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



import base64
from email.mime.text import MIMEText
from googleapiclient.discovery import build
from google.oauth2.credentials import Credentials
from django.template.loader import render_to_string
from django.utils.html import strip_tags
import os


TOKEN_PATH = os.path.join(os.path.dirname(__file__), 'token.pickle')

def send_verification_email(user, otp_code):
    """
    Send verification email using Gmail API
    """

    # user = 
    subject = 'Verify Your Email - P2P Kilosales'

    # Render HTML
    html_message = render_to_string('email_verification.html', {
        'user': user,
        'otp_code': otp_code
    })

    # Plain text version
    plain_message = strip_tags(html_message)

    try:
        print(f"Attempting to send verification email to {user.email}")

        # Load token.pickle
        creds = Credentials.from_authorized_user_file(
            TOKEN_PATH,
            ['https://www.googleapis.com/auth/gmail.send']
        )

        # Gmail service
        service = build('gmail', 'v1', credentials=creds)

        # Create MIME email
        message = MIMEText(html_message, 'html')
        message['to'] = user.email
        message['from'] = "gechderib@gmail.com"   # your Gmail
        message['subject'] = subject

        # Encode email
        raw_message = base64.urlsafe_b64encode(message.as_bytes()).decode()

        # Send email
        service.users().messages().send(
            userId="me",
            body={'raw': raw_message}
        ).execute()

        print(f"Verification email sent successfully to {user.email}")

    except Exception as e:
        print(f"Failed to send verification email to {user.email}: {e}")
        raise
