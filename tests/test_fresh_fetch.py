"""Fetch a fresh IMDb parental guide page and analyze its structure."""
import httpx
import random

imdb_id = "tt7131622"  # Perfect Days
url = f"https://www.imdb.com/title/{imdb_id}/parentalguide"

user_agents = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
]

ua = random.choice(user_agents)
headers = {
    "User-Agent": ua,
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
    "Accept-Encoding": "gzip, deflate, br",
    "Connection": "keep-alive",
    "Upgrade-Insecure-Requests": "1",
    "Sec-Fetch-Dest": "document",
    "Sec-Fetch-Mode": "navigate",
    "Sec-Fetch-Site": "none",
    "Sec-Fetch-User": "?1",
}

print(f"Fetching {url} ...")
with httpx.Client(follow_redirects=True, timeout=15.0) as client:
    resp = client.get(url, headers=headers)
    print(f"Status: {resp.status_code}")
    print(f"Content length: {len(resp.text)} chars")
    
    if resp.status_code == 202:
        print("GOT 202 — IMDb anti-scraping response")
        print(f"Preview: {resp.text[:500]}")
    elif len(resp.text) < 5000:
        print(f"SHORT response — likely WAF block")
        print(f"Content: {resp.text[:1000]}")
    else:
        from bs4 import BeautifulSoup
        soup = BeautifulSoup(resp.text, "html.parser")
        
        # Check for WAF
        if "AwsWafIntegration" in resp.text or "challenge-container" in resp.text:
            print("WAF CHALLENGE DETECTED in response!")
        
        print(f"\nTitle: {soup.title.string if soup.title else 'N/A'}")
        
        # Check all strategies
        print("\n--- Strategy 1: ipc-title__text ---")
        for h in soup.find_all(["h3", "h4"], class_="ipc-title__text"):
            print(f"  {h.get_text(strip=True)[:80]}")
        
        print("\n--- Strategy 2: advisory-* IDs ---")
        for lid in ["advisory-nudity", "advisory-violence", "advisory-profanity", "advisory-frightening"]:
            el = soup.find(id=lid)
            print(f"  {lid}: {'FOUND' if el else 'NOT FOUND'}")
        
        print("\n--- ipc-html-content-inner-div ---")
        items = soup.find_all(class_="ipc-html-content-inner-div")
        print(f"  Found {len(items)} items")
        for item in items[:3]:
            print(f"    {item.get_text(strip=True)[:120]}")
        
        # Look for new possible selectors
        print("\n--- All unique class patterns containing 'parent' or 'guide' or 'advisory' ---")
        seen = set()
        for tag in soup.find_all(True):
            for cls in tag.get("class", []):
                cl = cls.lower()
                if any(kw in cl for kw in ["parent", "guide", "advisory", "nudity", "violence", "profanity", "frighten"]):
                    if cls not in seen:
                        seen.add(cls)
                        print(f"  tag={tag.name} class={cls}")
        
        # Save the fresh HTML for inspection
        with open("fresh_imdb.html", "w", encoding="utf-8") as f:
            f.write(resp.text)
        print("\nSaved fresh HTML to fresh_imdb.html")
