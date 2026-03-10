"""
One-time local script to set up Gmail API OAuth2 credentials.

Steps:
1. Go to Google Cloud Console → create project → enable Gmail API
2. Create OAuth2 credentials (Desktop app) → download credentials.json to this directory
3. Run: python setup_gmail_oauth.py
4. Browser opens → sign in → authorize → token.json is saved
5. Upload token.json to HF Space secrets (or base64-encode as GMAIL_TOKEN_JSON env var)
"""
import os
import json
import base64
from google_auth_oauthlib.flow import InstalledAppFlow
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request

SCOPES = ["https://www.googleapis.com/auth/gmail.send"]
CREDENTIALS_FILE = os.path.join(os.path.dirname(__file__), "client_secret_972635069150-r8hiiobnotk6kc343scmgc2f64skh9v8.apps.googleusercontent.com.json")
TOKEN_FILE = os.path.join(os.path.dirname(__file__), "token.json")


def main():
    creds = None

    # Check for existing token
    if os.path.exists(TOKEN_FILE):
        creds = Credentials.from_authorized_user_file(TOKEN_FILE, SCOPES)

    # Refresh or run new flow
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            print("Refreshing expired token...")
            creds.refresh(Request())
        else:
            if not os.path.exists(CREDENTIALS_FILE):
                print(f"ERROR: {CREDENTIALS_FILE} not found.")
                print("Download it from Google Cloud Console -> APIs & Services -> Credentials -> OAuth 2.0 Client IDs")
                return

            print("Opening browser for OAuth2 authorization...")
            flow = InstalledAppFlow.from_client_secrets_file(CREDENTIALS_FILE, SCOPES)
            creds = flow.run_local_server(port=50200)

    # Save token
    with open(TOKEN_FILE, "w") as f:
        f.write(creds.to_json())
    print(f"Token saved to {TOKEN_FILE}")

    # Also print base64 version for env var usage
    token_b64 = base64.b64encode(creds.to_json().encode()).decode()
    print(f"\nBase64 token for GMAIL_TOKEN_JSON env var:")
    print(token_b64)


if __name__ == "__main__":
    main()
