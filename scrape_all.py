"""Massive scraper: restaurants + gyms across India and international cities."""
import sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

import asyncio
import logging
import yaml
import random
from database.db import init_db, insert_lead, sync_gmail_accounts
from scraper.google_maps_scraper import scrape_google_maps, search_email_for_business
from scraper.website_email_scraper import scrape_email_from_website
from scraper.lead_filter import is_valid_email_format

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

FRANCHISE_KEYWORDS = [
    "mcdonald", "kfc", "domino", "pizza hut", "subway", "burger king",
    "starbucks", "dunkin", "wendy", "taco bell", "papa john", "haldiram",
    "barbeque nation", "gold's gym", "anytime fitness", "planet fitness",
    "orangetheory", "f45 training",
]

# ===== ALL QUERIES =====
INDIA_QUERIES = []
INDIA_CITIES = [
    "Mumbai", "Delhi", "Bangalore", "Hyderabad", "Chennai", "Pune", "Kolkata",
    "Ahmedabad", "Jaipur", "Lucknow", "Chandigarh", "Indore", "Nagpur",
    "Coimbatore", "Kochi", "Goa", "Surat", "Noida", "Gurgaon", "Bhopal",
    "Visakhapatnam", "Mysore", "Mangalore", "Trivandrum", "Vadodara",
    "Rajkot", "Ludhiana", "Amritsar", "Dehradun", "Varanasi",
]
INDIA_AREAS = {
    "Mumbai": ["Andheri", "Bandra", "Juhu", "Powai", "Lower Parel", "Thane", "Navi Mumbai", "Malad", "Borivali"],
    "Delhi": ["Connaught Place", "Karol Bagh", "Hauz Khas", "Saket", "Rajouri Garden", "Lajpat Nagar", "Dwarka"],
    "Bangalore": ["Koramangala", "Indiranagar", "HSR Layout", "Whitefield", "JP Nagar", "Marathahalli", "Jayanagar"],
    "Hyderabad": ["Jubilee Hills", "Banjara Hills", "Hitech City", "Gachibowli", "Secunderabad", "Kukatpally"],
    "Chennai": ["Anna Nagar", "T Nagar", "Adyar", "Velachery", "Nungambakkam", "Mylapore"],
    "Pune": ["Koregaon Park", "Viman Nagar", "Hinjewadi", "Kothrud", "Aundh", "Baner"],
}
CATEGORIES = ["restaurants", "cafes", "dhabas", "gyms", "fitness centers"]

# Build India queries
for city in INDIA_CITIES:
    for cat in CATEGORIES:
        INDIA_QUERIES.append((f"{cat} in {city}", city, "India"))
    if city in INDIA_AREAS:
        for area in INDIA_AREAS[city]:
            INDIA_QUERIES.append((f"restaurants in {area} {city}", city, "India"))
            INDIA_QUERIES.append((f"gyms in {area} {city}", city, "India"))

# International queries
INTL_QUERIES = []
INTL_CITIES = {
    "USA": ["New York", "Los Angeles", "Chicago", "Houston", "Miami", "Dallas", "San Francisco",
            "Phoenix", "Atlanta", "Boston", "Seattle", "Denver", "Austin", "San Diego", "Las Vegas"],
    "UK": ["London", "Manchester", "Birmingham", "Leeds", "Edinburgh", "Glasgow", "Liverpool", "Bristol"],
    "UAE": ["Dubai", "Abu Dhabi", "Sharjah"],
    "Canada": ["Toronto", "Vancouver", "Montreal", "Calgary", "Ottawa"],
    "Australia": ["Sydney", "Melbourne", "Brisbane", "Perth", "Adelaide"],
    "Singapore": ["Singapore"],
    "Germany": ["Berlin", "Munich", "Frankfurt", "Hamburg"],
    "Netherlands": ["Amsterdam", "Rotterdam"],
}

for country, cities in INTL_CITIES.items():
    for city in cities:
        for cat in ["restaurants", "gyms", "fitness studios"]:
            INTL_QUERIES.append((f"{cat} in {city}", city, country))


def is_franchise(name):
    return any(k in (name or "").lower() for k in FRANCHISE_KEYWORDS)


async def scrape_query(query, city, country, headless=True):
    """Scrape a single query, find emails, save to DB."""
    leads_saved = 0
    try:
        results = await scrape_google_maps(query, max_results=10, headless=headless, min_delay=3, max_delay=6)
    except Exception as e:
        logger.error(f"Scrape failed: {query} -> {e}")
        return 0

    for r in results:
        if is_franchise(r.get("business_name")):
            continue

        # Try website email
        if not r.get("email") and r.get("website_url") and r.get("has_website"):
            email = await scrape_email_from_website(r["website_url"], headless=headless)
            if email and is_valid_email_format(email):
                r["email"] = email

        # Try Google search
        if not r.get("email"):
            email = await search_email_for_business(r["business_name"], city, headless=headless)
            if email and is_valid_email_format(email):
                r["email"] = email

        cat = r.get("category") or ("gym" if "gym" in query.lower() or "fitness" in query.lower() else "restaurant")
        insert_lead(
            business_name=r.get("business_name", ""),
            category=cat,
            phone=r.get("phone"),
            email=r.get("email"),
            location=r.get("location") or f"{city}, {country}",
            country=country,
            has_website=r.get("has_website", False),
            website_url=r.get("website_url"),
        )
        leads_saved += 1

    return leads_saved


async def main():
    init_db()
    with open("config/settings.yaml") as f:
        config = yaml.safe_load(f)
    sync_gmail_accounts(config.get("gmail_accounts", []))

    # Shuffle to spread across cities
    all_queries = INDIA_QUERIES + INTL_QUERIES
    random.shuffle(all_queries)

    total = 0
    total_queries = len(all_queries)

    print(f"\n{'='*60}")
    print(f"  MASSIVE SCRAPE: {total_queries} queries across India + International")
    print(f"{'='*60}\n")

    for i, (query, city, country) in enumerate(all_queries, 1):
        logger.info(f"[{i}/{total_queries}] {query}")
        saved = await scrape_query(query, city, country, headless=True)
        total += saved
        logger.info(f"  Saved {saved} leads (total: {total})")

        # Random delay between queries
        await asyncio.sleep(random.uniform(2, 5))

        # Progress report every 10 queries
        if i % 10 == 0:
            from database.db import get_email_stats
            stats = get_email_stats()
            print(f"\n  --- Progress: {i}/{total_queries} queries | {stats['total_leads']} leads | {stats['leads_with_email']} with email ---\n")

    print(f"\n{'='*60}")
    print(f"  SCRAPE DONE! Total new leads saved: {total}")
    from database.db import get_email_stats
    stats = get_email_stats()
    print(f"  Total leads in DB: {stats['total_leads']}")
    print(f"  With email: {stats['leads_with_email']}")
    print(f"  Pending to send: {stats['pending']}")
    print(f"{'='*60}\n")


if __name__ == "__main__":
    asyncio.run(main())
