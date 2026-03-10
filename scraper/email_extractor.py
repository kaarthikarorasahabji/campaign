import asyncio
import logging
from scraper.google_maps_scraper import search_email_for_business
from database.db import get_connection

logger = logging.getLogger(__name__)


async def enrich_leads_with_emails(headless=True, limit=50):
    """Find emails for leads that don't have one yet."""
    conn = get_connection()
    leads = conn.execute(
        """SELECT id, business_name, location FROM leads
           WHERE (email IS NULL OR email = '') AND has_website = 0
           LIMIT ?""",
        (limit,),
    ).fetchall()
    conn.close()

    enriched = 0
    for lead in leads:
        email = await search_email_for_business(lead["business_name"], lead["location"] or "", headless=headless)
        if email:
            conn = get_connection()
            conn.execute("UPDATE leads SET email = ? WHERE id = ?", (email, lead["id"]))
            conn.commit()
            conn.close()
            enriched += 1
            logger.info(f"Found email for {lead['business_name']}: {email}")
        await asyncio.sleep(2)

    logger.info(f"Enriched {enriched}/{len(leads)} leads with emails")
    return enriched
