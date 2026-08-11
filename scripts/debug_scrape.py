import asyncio
from playwright.async_api import async_playwright

URL = "https://www.imdb.com/title/tt7131622/parentalguide"
PROXY = "http://127.0.0.1:7897"

async def main():
    print(f"[Playwright] Launching Chrome with proxy {PROXY}...")
    async with async_playwright() as p:
        browser = await p.chromium.launch(
            channel="chrome",
            headless=True,
            proxy={"server": PROXY}
        )
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
        )
        page = await context.new_page()
        await page.add_init_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
        
        try:
            print("[Navigating] Going to IMDb...")
            await page.goto(URL, wait_until="domcontentloaded", timeout=45000)
            
            # Additional wait to allow WAF challenges to resolve
            await asyncio.sleep(5)
            
            title = await page.title()
            print(f"[Done] Title: {title}")
            
            sections = await page.evaluate("document.querySelectorAll('section').length")
            print(f"[Info] Found {sections} sections.")
            
            if sections > 0:
                print("SUCCESS: Playwright works with explicit proxy.")
            else:
                html = await page.content()
                print("FAIL: No sections found. Page content preview:")
                print(html[:500])
        except Exception as e:
            print(f"[Error] {e}")
            
        await browser.close()

if __name__ == "__main__":
    asyncio.run(main())
