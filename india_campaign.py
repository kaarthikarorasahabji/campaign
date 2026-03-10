"""
Worldwide cold email campaign.
Scrapes Google Maps across India + 35+ countries,
finds emails, sends personalized cold emails.
India -> Gmail SMTP | International -> Resend API.
Never sends to the same lead twice. Tracks scraped queries.
"""
import asyncio
import logging
import yaml
import time
import random
import os
from database.db import (
    init_db, insert_lead, get_unsent_leads, sync_gmail_accounts,
    record_email_sent, increment_sent_count,
    reset_daily_counts, get_email_stats, mark_query_scraped,
    is_query_scraped, get_total_unsent_count,
)
from scraper.google_maps_scraper import scrape_google_maps, search_email_for_business
from scraper.website_email_scraper import scrape_email_from_website
from scraper.lead_filter import is_valid_email_format
from scraper.query_generator import generate_all_queries, get_unscraped_queries
from emailer.gmail_sender import send_email, pick_gmail_account
from emailer.resend_sender import send_via_resend
from emailer.tracker import print_report
from jinja2 import Template

import sys
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s", stream=sys.stdout)
logger = logging.getLogger(__name__)

CONFIG_DIR = os.path.join(os.path.dirname(__file__), "config")

FRANCHISE_KEYWORDS = [
    "mcdonald", "kfc", "domino", "pizza hut", "subway", "burger king",
    "starbucks", "dunkin", "wendy", "taco bell", "papa john", "haldiram",
    "barbeque nation", "biryani blues", "wow momo", "chaayos",
]


def is_franchise(name):
    return any(k in (name or "").lower() for k in FRANCHISE_KEYWORDS)


def load_config():
    settings_path = os.path.join(CONFIG_DIR, "settings.yaml")
    if os.path.exists(settings_path):
        with open(settings_path, encoding="utf-8") as f:
            config = yaml.safe_load(f) or {}
    else:
        config = {}

    # Defaults for when settings.yaml is missing (Railway / production)
    config.setdefault("warmup_schedule", {3: 15, 7: 25, 14: 40, 999: 50})
    config.setdefault("target_categories", [
        "restaurants", "clinics", "dentists", "gyms", "pet shops",
        "car wash", "laundry", "salons", "spas", "cafes", "bakeries",
        "pharmacies", "coaching centers",
    ])
    config.setdefault("email_settings", {
        "min_delay_seconds": 20, "max_delay_seconds": 60,
        "daily_total_target": 200,
    })
    config.setdefault("scraper_settings", {
        "min_delay_seconds": 2, "max_delay_seconds": 5,
        "max_results_per_query": 15, "headless": True,
    })
    config.setdefault("sender", {
        "name": os.environ.get("SENDER_NAME", "Kaarthik Dass Arora"),
        "company": os.environ.get("SENDER_COMPANY", "Axenora Ai"),
        "phone": os.environ.get("SENDER_PHONE", "+91 7814051678"),
        "website": os.environ.get("SENDER_WEBSITE", "https://axenoraai.in"),
        "calendar_link": os.environ.get("SENDER_CALENDAR", "https://calendly.com/kaarthikdassarorasahabji"),
    })

    # Override secrets from environment variables (for Railway / production)
    # Gmail accounts from env
    gmail_accounts = config.get("gmail_accounts", [])
    env_accounts = []
    for i in range(1, 6):  # Support up to 5 accounts
        email = os.environ.get(f"GMAIL_{i}_EMAIL")
        password = os.environ.get(f"GMAIL_{i}_APP_PASSWORD")
        if email and password:
            env_accounts.append({"email": email, "app_password": password, "active": True})
    if env_accounts:
        config["gmail_accounts"] = env_accounts

    # Resend from env
    resend_key = os.environ.get("RESEND_API_KEY")
    if resend_key:
        resend = config.get("resend", {})
        resend["api_key"] = resend_key
        resend["from_email"] = os.environ.get("RESEND_FROM_EMAIL", resend.get("from_email", ""))
        resend["from_name"] = os.environ.get("RESEND_FROM_NAME", resend.get("from_name", ""))
        config["resend"] = resend

    return config


def load_template(country):
    """Load the right template based on country."""
    if country and country.lower() == "india":
        path = os.path.join(CONFIG_DIR, "email_templates", "template_india.html")
    else:
        path = os.path.join(CONFIG_DIR, "email_templates", "template_international.html")

    if os.path.exists(path):
        with open(path, encoding="utf-8") as f:
            return f.read()

    # Fallback to restaurant template
    fallback = os.path.join(CONFIG_DIR, "email_templates", "template_restaurant.html")
    with open(fallback, encoding="utf-8") as f:
        return f.read()


async def scrape_phase(config, max_queries=50):
    """
    Scrape Google Maps for business leads worldwide.
    Only runs queries that haven't been scraped before.
    """
    categories = config.get("target_categories", None)
    all_queries = generate_all_queries(categories=categories, include_international=True)

    # Filter to only unscraped queries
    unscraped = get_unscraped_queries(all_queries)

    if not unscraped:
        logger.info("All queries have been scraped! No new queries to run.")
        return 0

    batch = unscraped[:max_queries]
    logger.info(f"\nScraping {len(batch)} queries (of {len(unscraped)} remaining)...")

    scraper_settings = config.get("scraper_settings", {})
    min_delay = scraper_settings.get("min_delay_seconds", 2)
    max_delay = scraper_settings.get("max_delay_seconds", 5)
    max_results = scraper_settings.get("max_results_per_query", 10)

    total = 0
    for i, (query, city, country) in enumerate(batch, 1):
        logger.info(f"\n[{i}/{len(batch)}] Scraping: {query} [{country}]")

        try:
            results = await scrape_google_maps(
                query, max_results=max_results, headless=True,
                min_delay=min_delay, max_delay=max_delay,
            )
        except Exception as e:
            logger.error(f"Scrape failed for '{query}': {e}")
            mark_query_scraped(query, city, country, 0)
            continue

        saved = 0
        for r in results:
            if is_franchise(r.get("business_name")):
                continue

            # Try to find email from website
            if not r.get("email") and r.get("website_url") and r.get("has_website"):
                logger.info(f"  Checking website for {r['business_name']}...")
                try:
                    email = await scrape_email_from_website(r["website_url"], headless=True)
                    if email and is_valid_email_format(email):
                        r["email"] = email
                        logger.info(f"  Found: {email}")
                except Exception as e:
                    logger.debug(f"  Website scrape error: {e}")

            # Try Google search for email
            if not r.get("email"):
                logger.info(f"  Google searching email for {r['business_name']}...")
                try:
                    email = await search_email_for_business(r["business_name"], city, headless=True)
                    if email and is_valid_email_format(email):
                        r["email"] = email
                        logger.info(f"  Found: {email}")
                except Exception as e:
                    logger.debug(f"  Email search error: {e}")

            insert_lead(
                business_name=r.get("business_name", ""),
                category=r.get("category") or query.split(" in ")[0],
                phone=r.get("phone"),
                email=r.get("email"),
                location=r.get("location") or f"{city}, {country}",
                country=country,
                has_website=r.get("has_website", False),
                website_url=r.get("website_url"),
            )
            saved += 1

        mark_query_scraped(query, city, country, saved)
        total += saved
        logger.info(f"  Saved {saved} leads from '{query}'. Total this run: {total}")

        await asyncio.sleep(random.uniform(1, 3))

    return total


def send_phase(config):
    """
    Send cold emails to all unsent leads.
    Uses Resend API for ALL emails (Railway blocks SMTP port 587).
    Falls back to Gmail SMTP only if Resend is not configured.
    """
    sender_info = config.get("sender", {})
    warmup_schedule = config.get("warmup_schedule", {999: 100})
    email_settings = config.get("email_settings", {})
    resend_config = config.get("resend", {})
    daily_target = email_settings.get("daily_total_target", 200)
    min_delay = email_settings.get("min_delay_seconds", 15)
    max_delay = email_settings.get("max_delay_seconds", 45)

    # Check if Resend is available (required for Railway where SMTP is blocked)
    use_resend = bool(resend_config.get("api_key"))
    if not use_resend:
        logger.warning("⚠️  Resend API key not configured! Gmail SMTP may be blocked on Railway.")

    reset_daily_counts()

    leads = get_unsent_leads(limit=daily_target)
    if not leads:
        logger.info("No unsent leads with emails available.")
        return 0

    logger.info(f"\nSending emails to {len(leads)} leads...")
    logger.info(f"  Method: {'Resend API (HTTPS)' if use_resend else 'Gmail SMTP'}")

    # Pre-load templates
    india_template = Template(load_template("India"))
    intl_template = Template(load_template("International"))

    subject_templates = [
        "Never miss a phone order again, {name}",
        "{name} — your AI receptionist is ready",
        "Stop missing calls at {name}",
        "AI assistant for {name} — free demo",
    ]

    sent = 0
    failed = 0
    resend_sent = 0
    resend_limit = resend_config.get("daily_limit", 200)

    for lead in leads:
        country = lead["country"] or ""
        is_india = country.lower() == "india"

        # Pick the right template
        template = india_template if is_india else intl_template

        # Render email
        city = lead["location"] or "your area"
        if "," in city:
            city = city.split(",")[0].strip()

        html_body = template.render(
            business_name=lead["business_name"],
            category=lead["category"] or "business",
            city=city,
            sender_name=sender_info.get("name", ""),
            sender_company=sender_info.get("company", ""),
            sender_phone=sender_info.get("phone", ""),
            sender_website=sender_info.get("website", ""),
            calendar_link=sender_info.get("calendar_link", ""),
        )

        subject = random.choice(subject_templates).format(name=lead["business_name"])

        # Primary: Use Resend API for all emails (works on Railway)
        if use_resend and resend_sent < resend_limit:
            success = send_via_resend(lead["email"], subject, html_body, resend_config)
            sender_id = resend_config.get("from_email", "resend")
            if success:
                resend_sent += 1
        else:
            # Fallback: Gmail SMTP (only works locally, not on Railway)
            account = pick_gmail_account(warmup_schedule)
            if not account:
                logger.warning("All Gmail accounts at daily limit and Resend limit reached.")
                break
            success = send_email(lead["email"], subject, html_body, account)
            sender_id = account["email"]
            if success:
                increment_sent_count(account["email"])

        status = "sent" if success else "bounced"
        template_name = "india_cold" if is_india else "international_cold"
        record_email_sent(lead["id"], sender_id, template_name, status)

        if success:
            sent += 1
            tag = "🇮🇳" if is_india else "🌍"
            logger.info(f"  {tag} [{sent}] Sent to {lead['email']} ({lead['business_name']})")
        else:
            failed += 1
            logger.warning(f"  ❌ Failed: {lead['email']} ({lead['business_name']})")

        delay = random.uniform(min_delay, max_delay)
        time.sleep(delay)

    logger.info(f"\n✅ Done! Sent: {sent} (via Resend: {resend_sent}), Failed: {failed}")
    return sent


async def run_full_cycle(config, max_queries=50):
    """Run a complete scrape + send cycle."""
    print("\n" + "=" * 60)
    print("  AXENORA AI — WORLDWIDE EMAIL CAMPAIGN")
    print("=" * 60)

    stats = get_email_stats()
    print(f"\n  DB Status: {stats['total_leads']} leads, "
          f"{stats['leads_with_email']} with email, "
          f"{stats['pending']} pending, "
          f"{stats.get('queries_scraped', 0)} queries done")

    # Phase 1: Scrape
    print(f"\n[PHASE 1] Scraping Google Maps (up to {max_queries} queries)...")
    scraped = 0
    try:
        scraped = await scrape_phase(config, max_queries=max_queries)
        print(f"\nScraped {scraped} new leads.")
    except Exception as e:
        print(f"\nScrape phase failed: {e} — proceeding to send phase with existing leads.")

    # Phase 2: Send
    unsent = get_total_unsent_count()
    print(f"\n[PHASE 2] Sending emails ({unsent} pending)...")
    sent = send_phase(config)

    # Report
    print_report()
    stats = get_email_stats()
    print(f"\n  Queries scraped so far: {stats.get('queries_scraped', 0)}")
    print(f"  Remaining unsent leads: {stats['pending']}")

    return {"scraped": scraped, "sent": sent}


async def main():
    import argparse
    parser = argparse.ArgumentParser(description="Worldwide Cold Email Campaign")
    parser.add_argument("--scrape-only", action="store_true", help="Only scrape, don't send")
    parser.add_argument("--send-only", action="store_true", help="Only send, don't scrape")
    parser.add_argument("--report", action="store_true", help="Show stats only")
    parser.add_argument("--max-queries", type=int, default=50, help="Max queries per scrape run")
    parser.add_argument("--dry-run", action="store_true", help="Scrape but don't send")
    parser.add_argument("--india-only", action="store_true", help="Only scrape India queries")
    args = parser.parse_args()

    config = load_config()
    init_db()
    sync_gmail_accounts(config.get("gmail_accounts", []))

    if args.report:
        print_report()
        stats = get_email_stats()
        all_queries = generate_all_queries(config.get("target_categories"), include_international=True)
        unscraped = get_unscraped_queries(all_queries)
        india_q = sum(1 for _, _, c in all_queries if c == "India")
        intl_q = len(all_queries) - india_q
        print(f"  Total possible queries:  {len(all_queries)}")
        print(f"    India:                 {india_q}")
        print(f"    International:         {intl_q}")
        print(f"  Queries scraped:         {stats.get('queries_scraped', 0)}")
        print(f"  Queries remaining:       {len(unscraped)}")
        return

    if args.scrape_only:
        await scrape_phase(config, max_queries=args.max_queries)
        print_report()
        return

    if args.send_only:
        send_phase(config)
        print_report()
        return

    if args.dry_run:
        await scrape_phase(config, max_queries=args.max_queries)
        print("\n[DRY RUN] Skipping send phase.")
        print_report()
        return

    await run_full_cycle(config, max_queries=args.max_queries)


if __name__ == "__main__":
    asyncio.run(main())
