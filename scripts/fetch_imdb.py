import httpx
from src.scraper.http_scraper import HttpScraper

def fetch():
    scraper = HttpScraper()
    url = "https://www.imdb.com/title/tt2494362/parentalguide"
    headers = {
        "User-Agent": scraper.user_agents[0],
        "Accept-Language": "en-US,en;q=0.9",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8"
    }
    with httpx.Client(follow_redirects=True, timeout=15.0) as client:
        response = client.get(url, headers=headers)
        with open("test_imdb.html", "w", encoding="utf-8") as f:
            f.write(response.text)
        print("Written tt2494362 to test_imdb.html")

if __name__ == "__main__":
    fetch()
