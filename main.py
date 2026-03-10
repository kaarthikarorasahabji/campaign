import asyncio
import logging
import os
import yaml

from database.db import init_db, insert_lead, get_unsent_leads, sync_gmail_accounts
from scraper.google_maps_scraper import scrape_google_maps
from scraper.lead_filter import filter_leads, validate_lead_emails
from scraper.email_extractor import enrich_leads_with_emails
from emailer.gmail_sender import send_to_lead
from emailer.warmup import advance_warmup
from emailer.tracker import print_report, get_sent_today

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

CONFIG_PATH = os.path.join(os.path.dirname(__file__), "config", "settings.yaml")


def load_config():
    with open(CONFIG_PATH) as f:
        return yaml.safe_load(f)


def load_template(country, config_dir=None):
    if config_dir is None:
        config_dir = os.path.join(os.path.dirname(__file__), "config", "email_templates")
    if country and country.lower() == "india":
        path = os.path.join(config_dir, "template_india.html")
    else:
        path = os.path.join(config_dir, "template_international.html")

    if os.path.exists(path):
        with open(path) as f:
            return f.read()

    # Fallback to default template
    fallback = os.path.join(os.path.dirname(__file__), "templates", "cold_email.html")
    with open(fallback) as f:
        return f.read()


async def run_scraper(config):
    """Scrape Google Maps for all configured queries."""
    settings = config.get("scraper_settings", {})
    cities = config.get("target_cities", {})
    categories = config.get("target_categories", [])

    total_scraped = 0
    for country, city_list in cities.items():
        for city in city_list:
            for category in categories:
                query = f"{category} in {city}"
                logger.info(f"Scraping: {query}")

                results = await scrape_google_maps(
                    query,
                    max_results=settings.get("max_results_per_query", 20),
                    headless=settings.get("headless", True),
                    min_delay=settings.get("min_delay_seconds", 3),
                    max_delay=settings.get("max_delay_seconds", 8),
                )

                # Filter leads
                filtered = filter_leads(results)

                # Save to DB
                for lead in filtered:
                    insert_lead(
                        business_name=lead.get("business_name", ""),
                        category=lead.get("category") or category,
                        phone=lead.get("phone"),
                        email=lead.get("email"),
                        location=lead.get("location") or f"{city}, {country}",
                        country=country,
                        has_website=lead.get("has_website", False),
                        website_url=lead.get("website_url"),
                    )

                total_scraped += len(filtered)
                logger.info(f"Saved {len(filtered)} leads from '{query}'")

    return total_scraped


def run_email_campaign(config):
    """Send emails to unsent leads."""
    email_settings = config.get("email_settings", {})
    warmup_schedule = config.get("warmup_schedule", {3: 10, 7: 25, 14: 50, 999: 75})
    sender_info = config.get("sender", {})
    daily_target = email_settings.get("daily_total_target", 200)

    sent_today = get_sent_today()
    remaining = daily_target - sent_today
    if remaining <= 0:
        logger.info("Daily target already reached.")
        return 0

    leads = get_unsent_leads(limit=remaining)
    if not leads:
        logger.info("No unsent leads available.")
        return 0

    logger.info(f"Sending to {len(leads)} leads (target remaining: {remaining})")
    sent_count = 0

    for lead in leads:
        template_html = load_template(lead["country"])
        success = send_to_lead(
            lead,
            template_html,
            warmup_schedule,
            sender_info,
            min_delay=email_settings.get("min_delay_seconds", 30),
            max_delay=email_settings.get("max_delay_seconds", 120),
        )
        if success:
            sent_count += 1

    return sent_count


async def run_pipeline(config):
    """Full pipeline: scrape -> enrich -> send."""
    logger.info("=== Starting pipeline ===")

    # Step 1: Scrape
    scraped = await run_scraper(config)
    logger.info(f"Scraped {scraped} new leads")

    # Step 2: Enrich emails
    enriched = await enrich_leads_with_emails(
        headless=config.get("scraper_settings", {}).get("headless", True),
        limit=50,
    )
    logger.info(f"Enriched {enriched} leads with emails")

    # Step 3: Validate emails
    # (done inline during send)

    # Step 4: Send emails
    sent = run_email_campaign(config)
    logger.info(f"Sent {sent} emails")

    # Step 5: Advance warmup
    advance_warmup()

    # Step 6: Report
    print_report()

    return {"scraped": scraped, "enriched": enriched, "sent": sent}


def main():
    import argparse
    parser = argparse.ArgumentParser(description="Cold Email Automation for AI Calling Agents")
    parser.add_argument("--scrape", action="store_true", help="Run scraper only")
    parser.add_argument("--send", action="store_true", help="Run email sender only")
    parser.add_argument("--enrich", action="store_true", help="Enrich leads with emails")
    parser.add_argument("--report", action="store_true", help="Show campaign report")
    parser.add_argument("--init-db", action="store_true", help="Initialize database")
    parser.add_argument("--full", action="store_true", help="Run full pipeline")
    args = parser.parse_args()

    config = load_config()

    # Always init DB
    init_db()
    sync_gmail_accounts(config.get("gmail_accounts", []))

    if args.init_db:
        print("Database initialized.")
        return

    if args.report:
        print_report()
        return

    if args.scrape:
        asyncio.run(run_scraper(config))
        print_report()
        return

    if args.enrich:
        asyncio.run(enrich_leads_with_emails(
            headless=config.get("scraper_settings", {}).get("headless", True),
        ))
        return

    if args.send:
        run_email_campaign(config)
        print_report()
        return

    if args.full:
        asyncio.run(run_pipeline(config))
        return

    # Default: show help
    parser.print_help()


if __name__ == "__main__":
    main()
