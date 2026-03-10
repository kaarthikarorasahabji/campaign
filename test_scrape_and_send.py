"""Test: scrape restaurants, find emails, send test email."""
import asyncio
import logging
import yaml
import re
import random
from database.db import init_db, insert_lead, get_connection, sync_gmail_accounts
from scraper.google_maps_scraper import scrape_google_maps, search_email_for_business
from emailer.gmail_sender import send_email
from jinja2 import Template

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

FRANCHISE_KEYWORDS = [
    "mcdonald", "kfc", "domino", "pizza hut", "subway", "burger king",
    "starbucks", "dunkin", "wendy", "taco bell", "papa john", "haldiram",
    "barbeque nation", "social", "theobroma",
]


def is_franchise(name):
    name_lower = (name or "").lower()
    return any(k in name_lower for k in FRANCHISE_KEYWORDS)


async def main():
    init_db()

    with open("config/settings.yaml") as f:
        config = yaml.safe_load(f)
    sync_gmail_accounts(config.get("gmail_accounts", []))

    # Step 1: Scrape restaurants from Mumbai
    query = "restaurants in Mumbai"
    logger.info(f"Scraping: {query}")
    results = await scrape_google_maps(query, max_results=10, headless=True, min_delay=3, max_delay=6)

    logger.info(f"\nGot {len(results)} results:")
    for r in results:
        logger.info(f"  {r['business_name']} | phone={r.get('phone')} | website={r.get('has_website')}")

    # Filter out franchises
    leads = [r for r in results if not is_franchise(r.get("business_name"))]
    logger.info(f"\nAfter removing franchises: {len(leads)} leads")

    # Step 2: Find emails via Google search
    leads_with_email = []
    for lead in leads:
        if not lead.get("email"):
            logger.info(f"Searching email for: {lead['business_name']}")
            email = await search_email_for_business(
                lead["business_name"], "Mumbai", headless=True
            )
            if email:
                lead["email"] = email
                logger.info(f"  Found: {email}")
            else:
                logger.info(f"  No email found")

        # Save all to DB regardless
        insert_lead(
            business_name=lead.get("business_name", ""),
            category=lead.get("category") or "restaurant",
            phone=lead.get("phone"),
            email=lead.get("email"),
            location=lead.get("location") or "Mumbai, India",
            country="India",
            has_website=lead.get("has_website", False),
            website_url=lead.get("website_url"),
        )

        if lead.get("email"):
            leads_with_email.append(lead)

    logger.info(f"\nLeads with email: {len(leads_with_email)}")
    for l in leads_with_email:
        logger.info(f"  {l['business_name']} -> {l['email']}")

    # Step 3: Send TEST email to yourself using first lead's data for personalization
    gmail_acc = {
        "email": config["gmail_accounts"][0]["email"],
        "app_password": config["gmail_accounts"][0]["app_password"],
    }
    sender_info = config.get("sender", {})

    with open("config/email_templates/template_restaurant.html") as f:
        template_html = f.read()

    if leads_with_email:
        test_lead = leads_with_email[0]
    else:
        # Use first lead anyway for template test
        test_lead = leads[0] if leads else {"business_name": "Test Restaurant", "category": "restaurant"}

    template = Template(template_html)
    html_body = template.render(
        business_name=test_lead.get("business_name", "Test Restaurant"),
        category=test_lead.get("category") or "restaurant",
        city="Mumbai",
        sender_name=sender_info.get("name", "Your Name"),
        sender_company=sender_info.get("company", "Your AI Company"),
        sender_phone=sender_info.get("phone", ""),
        calendar_link=sender_info.get("calendar_link", ""),
    )

    subject = f"Never miss a phone order again, {test_lead.get('business_name', 'there')}"

    print("\n" + "=" * 60)
    print("  SENDING TEST EMAIL TO YOURSELF")
    print(f"  From: {gmail_acc['email']}")
    print(f"  To: {gmail_acc['email']}")
    print(f"  Subject: {subject}")
    print("=" * 60)

    success = send_email(gmail_acc["email"], subject, html_body, gmail_acc)
    if success:
        print("\n  TEST EMAIL SENT! Check your inbox.\n")
    else:
        print("\n  FAILED to send. Check app password.\n")

    # Summary
    print("=" * 60)
    print("  SCRAPE SUMMARY")
    print(f"  Total scraped:        {len(results)}")
    print(f"  After franchise filter: {len(leads)}")
    print(f"  With emails found:    {len(leads_with_email)}")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
