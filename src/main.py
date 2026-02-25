import argparse
import json
import sys
import os
from pydantic import ValidationError

from src.movie_resolver import TMDBResolver
from src.scraper.http_scraper import HttpScraper
from src.llm_reasoner import LLMReasoner

def map_dimension_key(dimension_name: str) -> str:
    """Standardizes string labels into consistent schema keys."""
    # "Sex & Nudity" -> "sex_and_nudity"
    # "Violence & Gore" -> "violence_and_gore"
    # "Profanity" -> "profanity"
    # "Frightening Scenes" -> "frightening_scenes"
    mapping = {
        "Sex & Nudity": "sex_and_nudity",
        "Violence & Gore": "violence_and_gore",
        "Profanity": "profanity",
        "Frightening Scenes": "frightening_scenes"
    }
    return mapping.get(dimension_name, dimension_name.lower().replace(" ", "_"))

def main():
    parser = argparse.ArgumentParser(description="ParentsHandbook - CLI to extract IMDb Parental Guides to aesthetic JSON")
    parser.add_argument("title", type=str, help="The title of the movie (e.g., 'The Matrix')")
    parser.add_argument("--refresh", action="store_true", help="Bypass the local cache and force a fresh scrape & analysis")
    args = parser.parse_args()

    # Define Cache Directory
    CACHE_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "cache")
    os.makedirs(CACHE_DIR, exist_ok=True)

    print(f"🎬 Starting ParentsHandbook Engine for: '{args.title}'\n")

    try:
        # 1. Resolve IMDb ID using TMDB
        print(f"🔍 [1/3] Searching TMDB to resolve exact IMDb ID...")
        resolver = TMDBResolver()
        imdb_id = resolver.search_movie(args.title)
        print(f"   ✅ Mathced IMDb ID: {imdb_id}\n")

        # 1.5. Check Local Cache
        cache_file_path = os.path.join(CACHE_DIR, f"{imdb_id}.json")
        if not args.refresh and os.path.exists(cache_file_path):
            print(f"📦 [CACHE HIT] Found existing evaluation for {imdb_id}")
            with open(cache_file_path, "r", encoding="utf-8") as f:
                cached_data = json.load(f)
            
            print(f"\n🎉 Pipeline Complete (Loaded from Cache)! Resulting JSON:\n")
            print(json.dumps(cached_data, indent=2, ensure_ascii=False))
            return # Exit early

        print(f"⏳ [CACHE MISS] Proceeding with live analysis...\n")

        # 2. Scrape guide sections using HTTP
        print(f"🕸️ [2/3] Scraping parental guide from IMDb...")
        scraper = HttpScraper()
        raw_guide_data = scraper.fetch_parental_guide(imdb_id)
        print(f"   ✅ Successfully fetched text for 4 dimensions.\n")

        # 3. LLM Parsing & Processing
        print(f"🧠 [3/3] Executing LLM Reasoner for semantic extraction...")
        reasoner = LLMReasoner()
        
        print(f"   -> Analyzing all 4 dimensions simultaneously with 'flash'...")
        final_report = reasoner.parse_all_dimensions(raw_guide_data)
        
        print(f"   -> Synthesizing overall verdict with 'pro'...")
        overall_data = reasoner.generate_overall_analysis(final_report)
        final_report["overall"] = overall_data

        # 4. Save to Cache
        with open(cache_file_path, "w", encoding="utf-8") as f:
            json.dump(final_report, f, indent=2, ensure_ascii=False)
        print(f"   💾 Saved results to cache: {cache_file_path}")

        print(f"\n🎉 Pipeline Complete! Resulting JSON:\n")
        print(json.dumps(final_report, indent=2, ensure_ascii=False))

    except Exception as e:
        print(f"\n❌ Pipeline failed during execution: {type(e).__name__}: {str(e)}")
        sys.exit(1)

if __name__ == "__main__":
    main()
