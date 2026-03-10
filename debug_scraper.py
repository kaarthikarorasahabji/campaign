"""Debug: inspect Google Maps DOM to find correct selectors."""
import asyncio
from playwright.async_api import async_playwright


async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False)
        page = await browser.new_page()

        await page.goto("https://www.google.com/maps/search/restaurants+in+Mumbai", wait_until="domcontentloaded", timeout=30000)
        await asyncio.sleep(5)

        # Click on the first listing
        listings = await page.locator('a[href*="/maps/place/"]').all()
        if listings:
            print(f"Found {len(listings)} listings")
            await listings[0].click()
            await asyncio.sleep(4)

            # Try to find the business name with various selectors
            selectors_to_try = [
                "h1",
                "h1.DUwDvf",
                'h1[class*="header"]',
                'div.lMbq3e h1',
                'div[role="main"] h1',
                'span.fontHeadlineLarge',
                '[data-attrid="title"]',
                'div.TIHn2',
                'div.tAiQdd h1',
                'div.qBF1Pd',
            ]

            for sel in selectors_to_try:
                try:
                    els = await page.locator(sel).all()
                    for el in els:
                        text = await el.inner_text(timeout=2000)
                        print(f"  {sel} -> '{text}'")
                except Exception as e:
                    print(f"  {sel} -> ERROR: {e}")

            # Also dump all h1 and h2
            print("\n--- All H1s ---")
            h1s = await page.locator("h1").all()
            for h in h1s:
                try:
                    text = await h.inner_text(timeout=1000)
                    cls = await h.get_attribute("class", timeout=1000)
                    print(f"  class='{cls}' text='{text}'")
                except:
                    pass

            # Check aria-label on the main panel
            print("\n--- Main panel aria-label ---")
            try:
                main = page.locator('div[role="main"]').first
                label = await main.get_attribute("aria-label", timeout=2000)
                print(f"  aria-label: '{label}'")
            except Exception as e:
                print(f"  ERROR: {e}")

            # Check data-item-id buttons
            print("\n--- data-item-id buttons ---")
            btns = await page.locator('button[data-item-id]').all()
            for btn in btns:
                try:
                    item_id = await btn.get_attribute("data-item-id", timeout=1000)
                    text = await btn.inner_text(timeout=1000)
                    print(f"  id='{item_id}' text='{text[:80]}'")
                except:
                    pass

            # Check for website link
            print("\n--- Website links ---")
            try:
                links = await page.locator('a[data-item-id="authority"]').all()
                for l in links:
                    href = await l.get_attribute("href", timeout=1000)
                    text = await l.inner_text(timeout=1000)
                    print(f"  href='{href}' text='{text}'")
            except:
                pass

        await browser.close()


asyncio.run(main())
