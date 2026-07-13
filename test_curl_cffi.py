"""Test curl_cffi vs httpx for IMDb anti-scraping bypass."""
from curl_cffi import requests as curl_requests
import httpx

imdb_id = "tt7131622"  # Perfect Days
url = f"https://www.imdb.com/title/{imdb_id}/parentalguide"

headers = {
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
}

# Test 1: httpx (current approach - expected to fail with 202)
print("=== Test 1: httpx ===")
try:
    with httpx.Client(follow_redirects=True, timeout=15.0) as client:
        resp = client.get(url, headers={**headers, "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"})
        print(f"  Status: {resp.status_code}")
        print(f"  Length: {len(resp.text)} chars")
        if resp.status_code == 202:
            print("  BLOCKED by anti-scraping (202)")
except Exception as e:
    print(f"  ERROR: {e}")

# Test 2: curl_cffi with Chrome impersonation
print("\n=== Test 2: curl_cffi (Chrome impersonation) ===")
try:
    resp = curl_requests.get(url, headers=headers, impersonate="chrome124", timeout=15)
    print(f"  Status: {resp.status_code}")
    print(f"  Length: {len(resp.text)} chars")
    if resp.status_code == 200 and len(resp.text) > 5000:
        # Check for actual content
        has_sex = "Sex" in resp.text and "Nudity" in resp.text
        has_violence = "Violence" in resp.text
        has_profanity = "Profanity" in resp.text
        print(f"  Has Sex & Nudity section: {has_sex}")
        print(f"  Has Violence section: {has_violence}")
        print(f"  Has Profanity section: {has_profanity}")
        if has_sex and has_violence:
            print("  SUCCESS! curl_cffi bypasses IMDb WAF!")
        
        # Quick parse test
        from bs4 import BeautifulSoup
        soup = BeautifulSoup(resp.text, "html.parser")
        h_tags = soup.find_all(["h3", "h4"], class_="ipc-title__text")
        print(f"  ipc-title__text headers found: {len(h_tags)}")
        for h in h_tags:
            print(f"    {h.get_text(strip=True)[:60]}")
    elif resp.status_code == 202:
        print("  Still blocked (202)")
    else:
        print(f"  Unexpected: preview={resp.text[:200]}")
except Exception as e:
    print(f"  ERROR: {type(e).__name__}: {e}")
