"""Send test email to self, then campaign to all pending leads."""
import sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

import logging
import yaml
import time
import random
from database.db import (
    init_db, get_connection, sync_gmail_accounts, record_email_sent,
    increment_sent_count, reset_daily_counts,
)
from emailer.gmail_sender import send_email, pick_gmail_account
from jinja2 import Template

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)


def load_config():
    with open("config/settings.yaml") as f:
        return yaml.safe_load(f)


def load_template():
    with open("config/email_templates/template_restaurant.html") as f:
        return f.read()


def get_pending_leads(limit=100):
    conn = get_connection()
    rows = conn.execute(
        """SELECT l.* FROM leads l
           LEFT JOIN emails_sent e ON l.id = e.lead_id
           WHERE e.id IS NULL AND l.email IS NOT NULL AND l.email != ''
           ORDER BY l.id ASC LIMIT ?""",
        (limit,),
    ).fetchall()
    conn.close()
    return rows


def main():
    config = load_config()
    init_db()
    sync_gmail_accounts(config.get("gmail_accounts", []))
    reset_daily_counts()

    warmup_schedule = config.get("warmup_schedule", {999: 100})
    sender_info = config.get("sender", {})
    email_settings = config.get("email_settings", {})
    min_delay = email_settings.get("min_delay_seconds", 30)
    max_delay = email_settings.get("max_delay_seconds", 120)

    template_html = load_template()
    template = Template(template_html)

    gmail_acc_1 = {
        "email": config["gmail_accounts"][0]["email"],
        "app_password": config["gmail_accounts"][0]["app_password"],
    }

    # ===== STEP 1: Send test to yourself =====
    test_html = template.render(
        business_name="Sample Restaurant",
        category="restaurant",
        city="Mumbai",
        sender_name=sender_info.get("name", ""),
        sender_company=sender_info.get("company", ""),
        sender_phone=sender_info.get("phone", ""),
        sender_website=sender_info.get("website", ""),
        calendar_link=sender_info.get("calendar_link", ""),
    )

    print("\n" + "=" * 60)
    print("  [1/2] SENDING TEST EMAIL TO YOU...")
    print(f"  To: {gmail_acc_1['email']}")
    success = send_email(gmail_acc_1["email"], "Test - AI Receptionist for Sample Restaurant", test_html, gmail_acc_1)
    if success:
        print("  TEST SENT! Check your inbox for the new design.")
    else:
        print("  TEST FAILED! Aborting.")
        return
    print("=" * 60)

    print("\n  Waiting 10s before starting campaign...")
    time.sleep(10)

    # ===== STEP 2: Send to all pending leads =====
    leads = get_pending_leads(limit=100)
    print(f"\n  [2/2] SENDING TO {len(leads)} RESTAURANT LEADS...")
    print("  Using Gmail rotation between accounts.\n")

    subject_templates = [
        "Never miss a customer call again, {name}",
        "{name} \u2014 your AI receptionist is ready",
        "Stop missing calls at {name}",
    ]

    sent = 0
    failed = 0

    for lead in leads:
        account = pick_gmail_account(warmup_schedule)
        if not account:
            print("\n  All accounts at daily limit. Stopping.")
            break

        city = lead["location"] or "your area"
        if "," in city:
            city = city.split(",")[0].strip()

        html_body = template.render(
            business_name=lead["business_name"],
            category=lead["category"] or "restaurant",
            city=city,
            sender_name=sender_info.get("name", ""),
            sender_company=sender_info.get("company", ""),
            sender_phone=sender_info.get("phone", ""),
            sender_website=sender_info.get("website", ""),
            calendar_link=sender_info.get("calendar_link", ""),
        )

        subject = random.choice(subject_templates).format(name=lead["business_name"])
        success = send_email(lead["email"], subject, html_body, account)
        status = "sent" if success else "bounced"
        record_email_sent(lead["id"], account["email"], "restaurant_cold", status)
        increment_sent_count(account["email"])

        if success:
            sent += 1
            print(f"  [{sent:3d}] SENT  -> {lead['email'][:35]:35s} ({lead['business_name'][:30]}) via {account['email'].split('@')[0]}")
        else:
            failed += 1
            print(f"  [ X ] FAIL  -> {lead['email'][:35]:35s} ({lead['business_name'][:30]})")

        delay = random.uniform(min_delay, max_delay)
        time.sleep(delay)

    print("\n" + "=" * 60)
    print(f"  CAMPAIGN COMPLETE")
    print(f"  Sent:   {sent}")
    print(f"  Failed: {failed}")
    print(f"  Total leads in DB with email: {sent + failed}")
    print("=" * 60)


if __name__ == "__main__":
    main()
