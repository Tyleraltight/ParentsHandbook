import httpx, json

# Check what data exists for Perfect Days (tt27503384) via GraphQL
resp = httpx.post(
    "https://graphql.imdb.com/",
    json={
        "query": """query { title(id: "tt27503384") { titleText { text } parentsGuide { guideItems(first: 100) { edges { node { category { id text } text { plainText } } } } } } }""",
        "variables": {},
    },
    headers={"Content-Type": "application/json", "x-imdb-client-name": "imdb-web-next-localized"},
    timeout=15,
)
data = resp.json()
edges = data.get("data",{}).get("title",{}).get("parentsGuide",{}).get("guideItems",{}).get("edges",[])
print(f"Movie: {data['data']['title']['titleText']['text']}")
print(f"Total items: {len(edges)}")
cats = {}
for e in edges:
    cat = e["node"]["category"]["text"]
    txt = e["node"]["text"]["plainText"]
    cats.setdefault(cat, []).append(txt)
for cat, texts in cats.items():
    print(f"\n{cat} ({len(texts)} items):")
    for t in texts:
        print(f"  - {t[:100]}")
