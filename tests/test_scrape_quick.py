"""Quick test: check what HttpScraper returns for Perfect Days (tt7131622)."""
import asyncio
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from src.scraper.http_scraper import HttpScraper

async def main():
    scraper = HttpScraper()
    imdb_id = "tt7131622"  # Perfect Days (2023)
    print(f"Testing scrape for {imdb_id} ...")
    
    try:
        result = await scraper.async_fetch_parental_guide(imdb_id)
        print(f"\n=== Scraper Result ===")
        for dim, text in result.items():
            print(f"\n--- {dim} ---")
            print(f"  Length: {len(text)} chars")
            if text:
                print(f"  Preview: {text[:200]}...")
            else:
                print(f"  ** EMPTY ** — this causes '数据缺失'")
    except Exception as e:
        print(f"ERROR: {type(e).__name__}: {e}")

asyncio.run(main())
