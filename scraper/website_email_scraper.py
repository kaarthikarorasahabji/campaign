"""Scrape emails from business websites by visiting their contact/about pages."""
import asyncio
import re
import random
import logging
from urllib.parse import urljoin
from playwright.async_api import async_playwright

logger = logging.getLogger(__name__)

EMAIL_REGEX = re.compile(r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}")
BLACKLIST = {"google", "gstatic", "example", "schema", "sentry", "w3.org", "wix", "squarespace", "wordpress", "facebook", "instagram", "twitter"}


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


async def scrape_email_from_website(website_url, headless=True):
    """Visit a website and try to find email addresses on main page and contact page."""
    if not website_url:
        return None

    # Clean URL
    if not website_url.startswith("http"):
        website_url = "https://" + website_url

    found_emails = []

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=headless)
        page = await browser.new_page()
        page.set_default_timeout(10000)

        try:
            # Visit main page
            await page.goto(website_url, wait_until="domcontentloaded", timeout=15000)
            await asyncio.sleep(random.uniform(1, 2))

            text = await page.inner_text("body", timeout=5000)
            found_emails.extend(EMAIL_REGEX.findall(text))

            # Also check href="mailto:" links
            mailto_links = await page.locator('a[href^="mailto:"]').all()
            for link in mailto_links:
                try:
                    href = await link.get_attribute("href", timeout=2000)
                    if href:
                        email = href.replace("mailto:", "").split("?")[0].strip()
                        found_emails.append(email)
                except Exception:
                    pass

            # Try to find and visit contact page
            contact_links = await page.locator('a:text-matches("contact|about|reach us|get in touch", "i")').all()
            for link in contact_links[:2]:  # Visit max 2 contact-like pages
                try:
                    href = await link.get_attribute("href", timeout=2000)
                    if href and not href.startswith("mailto:") and not href.startswith("tel:"):
                        contact_url = urljoin(website_url, href)
                        await page.goto(contact_url, wait_until="domcontentloaded", timeout=10000)
                        await asyncio.sleep(random.uniform(1, 2))

                        text = await page.inner_text("body", timeout=5000)
                        found_emails.extend(EMAIL_REGEX.findall(text))

                        # Check mailto links on contact page too
                        mailto_links = await page.locator('a[href^="mailto:"]').all()
                        for ml in mailto_links:
                            try:
                                href = await ml.get_attribute("href", timeout=2000)
                                if href:
                                    email = href.replace("mailto:", "").split("?")[0].strip()
                                    found_emails.append(email)
                            except Exception:
                                pass
                except Exception:
                    continue

        except Exception as e:
            logger.debug(f"Error scraping {website_url}: {e}")
        finally:
            await browser.close()

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
