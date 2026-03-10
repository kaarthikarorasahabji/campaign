import base64
import json
import random
import time
import logging
import os
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.image import MIMEImage
from jinja2 import Template
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from database.db import (
    get_active_gmail_accounts,
    increment_sent_count,
    record_email_sent,
    reset_daily_counts,
)

logger = logging.getLogger(__name__)

SCOPES = ["https://www.googleapis.com/auth/gmail.send"]
LOGO_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "config", "email_templates", "logo", "Logo.png")
FAVICON_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "config", "email_templates", "logo", "favicon.ico")
TOKEN_FILE = os.path.join(os.path.dirname(os.path.dirname(__file__)), "token.json")


def _get_gmail_service():
    """Build Gmail API service using OAuth2 token."""
    creds = None

    # Try token.json file first
    if os.path.exists(TOKEN_FILE):
        creds = Credentials.from_authorized_user_file(TOKEN_FILE, SCOPES)

    # Try base64-encoded env var (for HF Spaces / cloud)
    if not creds:
        token_b64 = os.environ.get("GMAIL_TOKEN_JSON")
        if token_b64:
            token_json = base64.b64decode(token_b64).decode()
            token_data = json.loads(token_json)
            creds = Credentials.from_authorized_user_info(token_data, SCOPES)

    if not creds:
        raise RuntimeError("No Gmail OAuth token found. Run setup_gmail_oauth.py first.")

    # Auto-refresh expired token
    if creds.expired and creds.refresh_token:
        creds.refresh(Request())
        # Save refreshed token back
        if os.path.exists(TOKEN_FILE):
            with open(TOKEN_FILE, "w") as f:
                f.write(creds.to_json())

    return build("gmail", "v1", credentials=creds, cache_discovery=False)


def get_daily_limit(warmup_day, warmup_schedule):
    """Get the daily send limit based on warmup day."""
    for day_threshold in sorted(warmup_schedule.keys()):
        if warmup_day <= int(day_threshold):
            return warmup_schedule[day_threshold]
    return 75  # default max per account per day


def pick_gmail_account(warmup_schedule):
    """Pick the best Gmail account to send from (least used today, under limit)."""
    reset_daily_counts()
    accounts = get_active_gmail_accounts()

    eligible = []
    for acc in accounts:
        limit = get_daily_limit(acc["warmup_day"], warmup_schedule)
        if acc["daily_sent"] < limit:
            eligible.append((acc, limit - acc["daily_sent"]))

    if not eligible:
        return None

    # Prefer account with most remaining capacity
    eligible.sort(key=lambda x: x[1], reverse=True)
    return eligible[0][0]


def send_email(to_email, subject, html_body, gmail_account):
    """Send a single email via Gmail API with inline logo + favicon."""
    msg = MIMEMultipart("related")
    msg["From"] = gmail_account["email"]
    msg["To"] = to_email
    msg["Subject"] = subject

    # Attach HTML
    alt = MIMEMultipart("alternative")
    alt.attach(MIMEText(html_body, "html", "utf-8"))
    msg.attach(alt)

    # Attach logo as inline CID
    if os.path.exists(LOGO_PATH):
        with open(LOGO_PATH, "rb") as f:
            logo_img = MIMEImage(f.read(), _subtype="png")
            logo_img.add_header("Content-ID", "<logo>")
            logo_img.add_header("Content-Disposition", "inline", filename="logo.png")
            msg.attach(logo_img)

    # Attach favicon as inline CID
    if os.path.exists(FAVICON_PATH):
        with open(FAVICON_PATH, "rb") as f:
            fav_img = MIMEImage(f.read(), _subtype="x-icon")
            fav_img.add_header("Content-ID", "<favicon>")
            fav_img.add_header("Content-Disposition", "inline", filename="favicon.ico")
            msg.attach(fav_img)

    try:
        service = _get_gmail_service()
        raw = base64.urlsafe_b64encode(msg.as_bytes()).decode()
        service.users().messages().send(
            userId="me",
            body={"raw": raw},
        ).execute()
        logger.info(f"Sent email to {to_email} from {gmail_account['email']}")
        return True
    except Exception as e:
        logger.error(f"Gmail API failed for {to_email}: {type(e).__name__}: {e}")
        return False


def send_to_lead(lead, template_html, warmup_schedule, sender_info, min_delay=30, max_delay=120):
    """Send a personalized email to a lead with account rotation."""
    account = pick_gmail_account(warmup_schedule)
    if not account:
        logger.warning("No Gmail accounts available (all at daily limit)")
        return False

    # Render template
    template = Template(template_html)
    html_body = template.render(
        business_name=lead["business_name"],
        category=lead["category"] or "your business",
        city=lead["location"] or "your area",
        sender_name=sender_info.get("name", ""),
        sender_company=sender_info.get("company", ""),
        sender_phone=sender_info.get("phone", ""),
        sender_website=sender_info.get("website", ""),
        calendar_link=sender_info.get("calendar_link", ""),
    )

    subject_templates = [
        f"Automate calls for {lead['business_name']} with AI",
        f"Never miss a customer call again, {lead['business_name']}",
        f"AI calling agent for {lead['category'] or 'your business'}",
    ]
    subject = random.choice(subject_templates)

    success = send_email(lead["email"], subject, html_body, account)
    status = "sent" if success else "bounced"

    record_email_sent(lead["id"], account["email"], "cold_email", status)
    increment_sent_count(account["email"])

    # Random delay between sends
    delay = random.uniform(min_delay, max_delay)
    logger.debug(f"Waiting {delay:.0f}s before next send")
    time.sleep(delay)

    return success
