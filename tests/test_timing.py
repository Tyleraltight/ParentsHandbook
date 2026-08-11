import asyncio
import time
from src.movie_resolver import TMDBResolver
from src.scraper.http_scraper import HttpScraper
from src.llm_reasoner import LLMReasoner

async def main():
    title = "Inception"
    print(f"Testing {title}...")
    
    start = time.time()
    resolver = TMDBResolver()
    imdb_id = await resolver.async_search_movie(title)
    print(f"TMDB Resolve: {time.time() - start:.2f}s (ID: {imdb_id})")
    
    start = time.time()
    scraper = HttpScraper()
    raw = await scraper.async_fetch_parental_guide(imdb_id)
    print(f"Scraper Fetch: {time.time() - start:.2f}s")
    
    start = time.time()
    reasoner = LLMReasoner()
    result = await reasoner.async_generate_full_report(raw)
    print(f"LLM Reasoning: {time.time() - start:.2f}s")
    
    print("Done!")

if __name__ == "__main__":
    asyncio.run(main())
