"""
Production campaign: Scrape restaurants -> find emails -> send cold emails.
Targets local/3-star restaurants (not franchises) across Indian cities.
"""
import asyncio
import logging
import yaml
import time
import random
from database.db import (
    init_db, insert_lead, get_unsent_leads, sync_gmail_accounts,
    record_email_sent, increment_sent_count, get_connection,
    reset_daily_counts, get_email_stats,
)
from scraper.google_maps_scraper import scrape_google_maps, search_email_for_business
from scraper.website_email_scraper import scrape_email_from_website
from scraper.lead_filter import is_valid_email_format
from emailer.gmail_sender import send_email, pick_gmail_account
from emailer.tracker import print_report
from jinja2 import Template

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

FRANCHISE_KEYWORDS = [
    "mcdonald", "kfc", "domino", "pizza hut", "subway", "burger king",
    "starbucks", "dunkin", "wendy", "taco bell", "papa john", "haldiram",
    "barbeque nation", "biryani blues", "wow momo", "chaayos",
]


def is_franchise(name):
    return any(k in (name or "").lower() for k in FRANCHISE_KEYWORDS)


def load_config():
    with open("config/settings.yaml") as f:
        return yaml.safe_load(f)


def load_template():
    with open("config/email_templates/template_restaurant.html") as f:
        return f.read()


async def scrape_phase(config):
    """Scrape Google Maps for restaurant leads."""
    queries = [
        # Punjab
        ("restaurants in Chandigarh", "Chandigarh", "India"),
        ("restaurants in Ludhiana", "Ludhiana", "India"),
        ("restaurants in Amritsar", "Amritsar", "India"),
        ("restaurants in Jalandhar", "Jalandhar", "India"),
        ("dhabas in Mohali", "Mohali", "India"),
        ("restaurants in Patiala", "Patiala", "India"),
        # Delhi
        ("restaurants in Connaught Place Delhi", "Delhi", "India"),
        ("restaurants in Karol Bagh Delhi", "Delhi", "India"),
        ("restaurants in Lajpat Nagar Delhi", "Delhi", "India"),
        ("restaurants in Rajouri Garden Delhi", "Delhi", "India"),
        ("dhabas in Delhi", "Delhi", "India"),
        # Bangalore
        ("restaurants in Koramangala Bangalore", "Bangalore", "India"),
        ("restaurants in Indiranagar Bangalore", "Bangalore", "India"),
        ("restaurants in Jayanagar Bangalore", "Bangalore", "India"),
        ("restaurants in Whitefield Bangalore", "Bangalore", "India"),
    ]

    total = 0
    for query, city, country in queries:
        logger.info(f"\nScraping: {query}")
        try:
            results = await scrape_google_maps(
                query, max_results=10, headless=True, min_delay=1, max_delay=3
            )
        except Exception as e:
            logger.error(f"Scrape failed for '{query}': {e}")
            continue

        for r in results:
            if is_franchise(r.get("business_name")):
                continue

            # Try to get email from website
            if not r.get("email") and r.get("website_url") and r.get("has_website"):
                logger.info(f"  Checking website for {r['business_name']}...")
                email = await scrape_email_from_website(r["website_url"], headless=True)
                if email and is_valid_email_format(email):
                    r["email"] = email
                    logger.info(f"  Found: {email}")

            # Try Google search for email
            if not r.get("email"):
                logger.info(f"  Google searching email for {r['business_name']}...")
                email = await search_email_for_business(r["business_name"], city, headless=True)
                if email and is_valid_email_format(email):
                    r["email"] = email
                    logger.info(f"  Found: {email}")

            insert_lead(
                business_name=r.get("business_name", ""),
                category=r.get("category") or "restaurant",
                phone=r.get("phone"),
                email=r.get("email"),
                location=r.get("location") or f"{city}, {country}",
                country=country,
                has_website=r.get("has_website", False),
                website_url=r.get("website_url"),
            )
            total += 1

        logger.info(f"Saved leads from '{query}'. Total so far: {total}")
        await asyncio.sleep(random.uniform(2, 5))

    return total


def send_phase(config):
    """Send cold emails to leads with email addresses."""
    template_html = load_template()
    sender_info = config.get("sender", {})
    warmup_schedule = config.get("warmup_schedule", {999: 100})
    email_settings = config.get("email_settings", {})
    daily_target = email_settings.get("daily_total_target", 100)
    min_delay = email_settings.get("min_delay_seconds", 30)
    max_delay = email_settings.get("max_delay_seconds", 120)

    reset_daily_counts()

    # Get unsent leads with emails
    leads = get_unsent_leads(limit=daily_target)
    if not leads:
        logger.info("No unsent leads with emails available.")
        return 0

    logger.info(f"\nSending emails to {len(leads)} leads...")
    template = Template(template_html)
    sent = 0
    failed = 0

    subject_templates = [
        "Never miss a phone order again, {name}",
        "{name} — your AI receptionist is ready",
        "Stop missing calls at {name}",
    ]

    for lead in leads:
        # Pick Gmail account
        account = pick_gmail_account(warmup_schedule)
        if not account:
            logger.warning("All accounts at daily limit. Stopping.")
            break

        # Render email
        city = lead["location"] or "your area"
        # Extract just city name if full address
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
            logger.info(f"  [{sent}] Sent to {lead['email']} ({lead['business_name']})")
        else:
            failed += 1
            logger.warning(f"  Failed: {lead['email']} ({lead['business_name']})")

        # Delay between sends
        delay = random.uniform(min_delay, max_delay)
        logger.debug(f"  Waiting {delay:.0f}s...")
        time.sleep(delay)

    logger.info(f"\nDone! Sent: {sent}, Failed: {failed}")
    return sent


async def main():
    config = load_config()
    init_db()
    sync_gmail_accounts(config.get("gmail_accounts", []))

    print("\n" + "=" * 60)
    print("  AI RECEPTIONIST COLD EMAIL CAMPAIGN")
    print("  Target: Local restaurants in India")
    print("=" * 60)

    # Phase 1: Scrape
    print("\n[PHASE 1] Scraping Google Maps for restaurants...")
    scraped = await scrape_phase(config)
    print(f"\nScraped {scraped} leads total.")

    # Show how many have emails
    stats = get_email_stats()
    print(f"Leads with email: {stats['leads_with_email']}")
    print(f"Pending to send: {stats['pending']}")

    # Phase 2: Send
    print("\n[PHASE 2] Sending cold emails...")
    sent = send_phase(config)

    # Report
    print_report()


if __name__ == "__main__":
    asyncio.run(main())
