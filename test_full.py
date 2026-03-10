"""Full test: local restaurant queries + website email scraping + send test."""
import asyncio
import logging
import yaml
from database.db import init_db, insert_lead, get_connection, sync_gmail_accounts
from scraper.google_maps_scraper import scrape_google_maps, search_email_for_business
from scraper.website_email_scraper import scrape_email_from_website
from emailer.gmail_sender import send_email
from jinja2 import Template

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

FRANCHISE_KEYWORDS = [
    "mcdonald", "kfc", "domino", "pizza hut", "subway", "burger king",
    "starbucks", "dunkin", "wendy", "taco bell", "papa john", "haldiram",
    "barbeque nation",
]


def is_franchise(name):
    return any(k in (name or "").lower() for k in FRANCHISE_KEYWORDS)


async def main():
    init_db()
    with open("config/settings.yaml") as f:
        config = yaml.safe_load(f)
    sync_gmail_accounts(config.get("gmail_accounts", []))

    # Local search queries to find smaller restaurants
    queries = [
        ("local restaurants in Mumbai", "Mumbai", "India"),
        ("dhabas in Mumbai", "Mumbai", "India"),
        ("restaurants near Andheri Mumbai", "Mumbai", "India"),
        ("family restaurants in Delhi", "Delhi", "India"),
        ("dhabas in Delhi", "Delhi", "India"),
    ]

    all_leads = []
    for query, city, country in queries:
        logger.info(f"\n=== Scraping: {query} ===")
        results = await scrape_google_maps(query, max_results=8, headless=True, min_delay=3, max_delay=6)
        for r in results:
            if not is_franchise(r.get("business_name")):
                r["city"] = city
                r["country"] = country
                all_leads.append(r)
        logger.info(f"Got {len(results)} results, {len(all_leads)} total leads so far")
        await asyncio.sleep(2)

    logger.info(f"\n=== Total leads: {len(all_leads)} ===")

    # Step 2: Try to find emails
    # First: scrape websites of leads that have websites
    for lead in all_leads:
        if lead.get("email"):
            continue
        if lead.get("website_url") and lead.get("has_website"):
            logger.info(f"Checking website: {lead['business_name']} -> {lead['website_url']}")
            email = await scrape_email_from_website(lead["website_url"], headless=True)
            if email:
                lead["email"] = email
                logger.info(f"  Found email on website: {email}")

    # Second: Google search for remaining leads without email
    for lead in all_leads:
        if lead.get("email"):
            continue
        logger.info(f"Google searching email for: {lead['business_name']}")
        email = await search_email_for_business(lead["business_name"], lead.get("city", ""), headless=True)
        if email:
            lead["email"] = email
            logger.info(f"  Found via Google: {email}")

    # Save all to DB
    for lead in all_leads:
        insert_lead(
            business_name=lead.get("business_name", ""),
            category=lead.get("category") or "restaurant",
            phone=lead.get("phone"),
            email=lead.get("email"),
            location=lead.get("location") or f"{lead.get('city', '')}, {lead.get('country', '')}",
            country=lead.get("country", "India"),
            has_website=lead.get("has_website", False),
            website_url=lead.get("website_url"),
        )

    leads_with_email = [l for l in all_leads if l.get("email")]

    # Print summary
    print("\n" + "=" * 60)
    print("  SCRAPE RESULTS")
    print(f"  Total leads:        {len(all_leads)}")
    print(f"  With email found:   {len(leads_with_email)}")
    print()
    for l in leads_with_email:
        print(f"  {l['business_name']:40s} {l['email']}")
    print("=" * 60)

    # Send test email to yourself
    gmail_acc = {
        "email": config["gmail_accounts"][0]["email"],
        "app_password": config["gmail_accounts"][0]["app_password"],
    }
    sender_info = config.get("sender", {})

    with open("config/email_templates/template_restaurant.html") as f:
        template_html = f.read()

    test_lead = leads_with_email[0] if leads_with_email else all_leads[0] if all_leads else None
    if test_lead:
        template = Template(template_html)
        html_body = template.render(
            business_name=test_lead.get("business_name", "there"),
            category="restaurant",
            city=test_lead.get("city", "your area"),
            sender_name=sender_info.get("name", ""),
            sender_company=sender_info.get("company", ""),
            sender_phone=sender_info.get("phone", ""),
            calendar_link=sender_info.get("calendar_link", ""),
        )
        subject = f"Never miss a phone order again, {test_lead['business_name']}"

        print(f"\n  Sending test email to yourself: {gmail_acc['email']}")
        success = send_email(gmail_acc["email"], subject, html_body, gmail_acc)
        print(f"  {'SENT!' if success else 'FAILED'}\n")


if __name__ == "__main__":
    asyncio.run(main())
