import httpx
from bs4 import BeautifulSoup
import json

url = "https://www.imdb.com/title/tt2491504/parentalguide"
headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    "Accept-Language": "en-US,en;q=0.9",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8"
}

response = httpx.get(url, headers=headers)
soup = BeautifulSoup(response.text, "html.parser")

# Let's search for the word 'Violence' and print its parent tags
for elem in soup.find_all(string=lambda t: t and 'Violence' in t):
    parent = elem.parent
    if parent:
        print(f"Text: '{elem.strip()}' -> Parent Tag: <{parent.name} class='{parent.get('class', [])}' id='{parent.get('id', '')}'>")
        # Go up a bit to see the container
        for ans in list(parent.parents)[:5]:
            print(f"  Ancestor: <{ans.name} class='{ans.get('class', [])}' id='{ans.get('id', '')}'>")

print("--- Checking old IDs ---")
for dim in ["advisory-nudity", "advisory-violence", "advisory-profanity", "advisory-frightening"]:
    sec = soup.find(id=dim)
    if sec:
        print(f"FOUND ID {dim} -> text length: {len(sec.get_text())}")
    else:
        print(f"ID {dim} NOT FOUND")
