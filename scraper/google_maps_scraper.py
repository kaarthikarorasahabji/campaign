import asyncio
import random
import re
import logging
from urllib.parse import quote_plus
from playwright.async_api import async_playwright

logger = logging.getLogger(__name__)

CHROMIUM_ARGS = [
    "--disable-gpu",
    "--disable-dev-shm-usage",
    "--disable-extensions",
    "--no-sandbox",
    "--single-process",
    "--disable-setuid-sandbox",
    "--js-flags=--max-old-space-size=128",
]


async def scrape_google_maps(query, max_results=20, headless=True, min_delay=3, max_delay=8):
    """
    Scrape Google Maps for a given search query.
    Returns a list of dicts with business info.
    """
    results = []
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=headless, args=CHROMIUM_ARGS)
        page = await browser.new_page()
        try:
            url = f"https://www.google.com/maps/search/{quote_plus(query)}"
            await page.goto(url, wait_until="domcontentloaded", timeout=30000)
            await asyncio.sleep(random.uniform(min_delay, max_delay))

            # Scroll the results panel to load more results
            results_panel = page.locator('div[role="feed"]')
            for _ in range(5):
                try:
                    await results_panel.evaluate("el => el.scrollTop = el.scrollHeight")
                    await asyncio.sleep(random.uniform(1.5, 3))
                except Exception:
                    break

            # Get all listing links
            listings = await page.locator('a[href*="/maps/place/"]').all()
            listings = listings[:max_results]

            for listing in listings:
                try:
                    # Get name from listing card before clicking
                    name = None
                    try:
                        name_el = listing.locator("div.qBF1Pd").first
                        name = await name_el.inner_text(timeout=2000)
                    except Exception:
                        pass

                    # Get the aria-label which often has the name
                    if not name:
                        try:
                            name = await listing.get_attribute("aria-label", timeout=2000)
                        except Exception:
                            pass

                    if not name:
                        continue

                    await listing.click()
                    await asyncio.sleep(random.uniform(min_delay, max_delay))

                    biz = await _extract_business_info(page, name)
                    if biz and biz.get("business_name"):
                        results.append(biz)
                        logger.info(f"Scraped: {biz['business_name']}")
                except Exception as e:
                    logger.warning(f"Error extracting listing: {e}")
                    continue

        except Exception as e:
            logger.error(f"Scraper error for query '{query}': {e}")
        finally:
            await browser.close()

    return results


async def _extract_business_info(page, name_from_listing=None):
    """Extract business details from the Maps detail panel."""
    info = {
        "business_name": name_from_listing,
        "category": None,
        "phone": None,
        "email": None,
        "website_url": None,
        "has_website": False,
        "location": None,
    }

    if not info["business_name"]:
        return None

    # Try to get category from the detail panel
    try:
        cat_el = page.locator('button[jsaction*="category"]').first
        info["category"] = await cat_el.inner_text(timeout=2000)
    except Exception:
        pass

    # Extract from data-item-id buttons (address, phone, website)
    try:
        btns = await page.locator('button[data-item-id]').all()
        for btn in btns:
            try:
                item_id = await btn.get_attribute("data-item-id", timeout=1000)
                text = await btn.inner_text(timeout=1000)
                text = text.strip()

                if item_id and "phone" in item_id:
                    info["phone"] = text
                elif item_id and "address" in item_id:
                    info["location"] = text
            except Exception:
                continue
    except Exception:
        pass

    # Check for website link
    try:
        web_link = page.locator('a[data-item-id="authority"]').first
        href = await web_link.get_attribute("href", timeout=2000)
        if href:
            info["website_url"] = href
            info["has_website"] = True
    except Exception:
        pass

    # Fallback: check tooltip-based elements
    if not info["phone"]:
        try:
            el = page.locator('[data-tooltip="Copy phone number"]').first
            info["phone"] = (await el.inner_text(timeout=1000)).strip()
        except Exception:
            pass

    if not info["location"]:
        try:
            el = page.locator('[data-tooltip="Copy address"]').first
            info["location"] = (await el.inner_text(timeout=1000)).strip()
        except Exception:
            pass

    if not info["has_website"]:
        try:
            el = page.locator('[data-tooltip="Open website"]').first
            text = await el.inner_text(timeout=1000)
            if text.strip():
                info["website_url"] = text.strip()
                info["has_website"] = True
        except Exception:
            pass

    # Fallback: look for website in any aria-label containing "website"
    if not info["has_website"]:
        try:
            web_els = await page.locator('a[aria-label*="ebsite"]').all()
            if web_els:
                info["has_website"] = True
                info["website_url"] = await web_els[0].get_attribute("href", timeout=1000)
        except Exception:
            pass

    return info


async def search_email_for_business(business_name, location, headless=True):
    """Search Google for a business's email when not listed on Maps."""
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=headless, args=CHROMIUM_ARGS)
        page = await browser.new_page()
        try:
            query = f'{business_name} {location} email contact'
            await page.goto(f"https://www.google.com/search?q={quote_plus(query)}", timeout=15000)
            await asyncio.sleep(random.uniform(2, 4))

            content = await page.inner_text("body", timeout=5000)
            emails = re.findall(r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}", content)
            # Filter out common false positives
            filtered = [
                e for e in emails
                if not any(x in e.lower() for x in ["google", "gstatic", "example", "schema", "sentry", "w3.org", "wix", "mailto"])
            ]
            return filtered[0] if filtered else None
        except Exception as e:
            logger.warning(f"Email search failed for {business_name}: {e}")
            return None
        finally:
            await browser.close()


if __name__ == "__main__":
    import sys
    query = sys.argv[1] if len(sys.argv) > 1 else "restaurants in Mumbai"
    results = asyncio.run(scrape_google_maps(query, max_results=5, headless=False))
    for r in results:
        print(r)
