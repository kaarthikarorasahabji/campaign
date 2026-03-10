"""Scrape emails from business websites using httpx (no browser needed)."""
import asyncio
import re
import random
import logging
import httpx
from urllib.parse import urljoin
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

EMAIL_REGEX = re.compile(r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}")
BLACKLIST = {"google", "gstatic", "example", "schema", "sentry", "w3.org", "wix", "squarespace", "wordpress", "facebook", "instagram", "twitter"}

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
}


def _filter_emails(emails):
    seen = set()
    result = []
    for e in emails:
        e = e.lower().strip()
        if e in seen:
            continue
        if any(x in e for x in BLACKLIST):
            continue
        if e.endswith(".png") or e.endswith(".jpg") or e.endswith(".svg"):
            continue
        seen.add(e)
        result.append(e)
    return result


def _extract_emails_from_html(html):
    """Extract emails from HTML text and mailto links."""
    emails = EMAIL_REGEX.findall(html)
    soup = BeautifulSoup(html, "html.parser")
    for link in soup.find_all("a", href=True):
        href = link["href"]
        if href.startswith("mailto:"):
            email = href.replace("mailto:", "").split("?")[0].strip()
            emails.append(email)
    return emails


async def scrape_email_from_website(website_url, headless=True):
    """Visit a website and try to find email addresses on main page and contact page."""
    if not website_url:
        return None

    if not website_url.startswith("http"):
        website_url = "https://" + website_url

    found_emails = []

    async with httpx.AsyncClient(headers=HEADERS, timeout=15, follow_redirects=True, verify=False) as client:
        try:
            resp = await client.get(website_url)
            html = resp.text
            found_emails.extend(_extract_emails_from_html(html))

            # Try to find and visit contact page
            soup = BeautifulSoup(html, "html.parser")
            contact_links = []
            for link in soup.find_all("a", href=True):
                text = (link.get_text() or "").lower()
                href = link["href"].lower()
                if any(k in text or k in href for k in ["contact", "about", "reach", "get-in-touch"]):
                    contact_links.append(link["href"])

            for href in contact_links[:2]:
                try:
                    contact_url = urljoin(website_url, href)
                    resp = await client.get(contact_url)
                    found_emails.extend(_extract_emails_from_html(resp.text))
                except Exception:
                    continue

        except Exception as e:
            logger.debug(f"Error scraping {website_url}: {e}")

    filtered = _filter_emails(found_emails)
    return filtered[0] if filtered else None


async def enrich_leads_from_websites(leads, headless=True):
    """For leads with websites but no email, try to scrape email from their website."""
    enriched = 0
    for lead in leads:
        if lead.get("email"):
            continue
        if not lead.get("website_url"):
            continue

        logger.info(f"Scraping website for email: {lead['business_name']} -> {lead['website_url']}")
        email = await scrape_email_from_website(lead["website_url"], headless=headless)
        if email:
            lead["email"] = email
            enriched += 1
            logger.info(f"  Found: {email}")
        else:
            logger.info(f"  No email found on website")

        await asyncio.sleep(random.uniform(1, 3))

    logger.info(f"Enriched {enriched} leads from websites")
    return leads


if __name__ == "__main__":
    import sys
    url = sys.argv[1] if len(sys.argv) > 1 else "https://thebombaycanteen.com"
    email = asyncio.run(scrape_email_from_website(url, headless=False))
    print(f"Found email: {email}")
