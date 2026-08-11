"""Analyze the dump.html to understand current IMDb page structure."""
from bs4 import BeautifulSoup

with open("dump.html", "r", encoding="latin-1") as f:
    soup = BeautifulSoup(f.read(), "html.parser")

print("=== All h3 tags ===")
for h in soup.find_all("h3")[:20]:
    cls = h.get("class", [])
    text = h.get_text(strip=True)[:80]
    print(f"  class={cls}  text={text}")

print(f"\n=== Section count: {len(soup.find_all('section'))} ===")

print("\n=== Looking for advisory-* IDs ===")
for legacy_id in ["advisory-nudity", "advisory-violence", "advisory-profanity", "advisory-frightening"]:
    el = soup.find(id=legacy_id)
    print(f"  {legacy_id}: {'FOUND' if el else 'NOT FOUND'}")

print("\n=== Looking for ipc-html-content-inner-div ===")
items = soup.find_all(class_="ipc-html-content-inner-div")
print(f"  Found {len(items)} items")
for item in items[:5]:
    print(f"    {item.get_text(strip=True)[:100]}")

print("\n=== Page title ===")
print(f"  {soup.title.string if soup.title else 'NO TITLE'}")

print(f"\n=== Total HTML length: {len(str(soup))} chars ===")
