import os
import base64
from email.mime.text import MIMEText
from googleapiclient.discovery import build
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CREDENTIALS_FILE = "credentials.json"
TOKEN_FILE = "token.json"
print("the token file is: ", TOKEN_FILE)
SCOPES = ["https://www.googleapis.com/auth/gmail.send"]

def load_credentials():
    creds = None
    if os.path.exists(TOKEN_FILE):
        creds = Credentials.from_authorized_user_file(TOKEN_FILE, SCOPES)
    if creds and creds.expired and creds.refresh_token:
        creds.refresh(Request())
        with open(TOKEN_FILE, "w") as f:
            f.write(creds.to_json())
    if not creds:
        raise RuntimeError("No token.json found — run the OAuth flow to generate it")
    return creds

def build_gmail_service():
    creds = load_credentials()
    service = build("gmail", "v1", credentials=creds)
    return service

def send_message(sender, to, subject, plain_text=None, html_text=None):
    if html_text:
        msg = MIMEText(html_text, "html")
    else:
        msg = MIMEText(plain_text, "plain")
    
    msg["to"] = to
    msg["from"] = sender
    msg["subject"] = subject

    raw = base64.urlsafe_b64encode(msg.as_bytes()).decode()
    service = build_gmail_service()
    sent = service.users().messages().send(userId="me", body={"raw": raw}).execute()
    return sent
