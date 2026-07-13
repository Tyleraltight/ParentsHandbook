"""Build the complete working GraphQL query for IMDb parental guide."""
from curl_cffi import requests as curl_requests
import json

GQL_URL = "https://graphql.imdb.com/"
HEADERS = {
    "Content-Type": "application/json",
    "x-imdb-client-name": "imdb-web-next-localized",
}

def gql(query, variables=None):
    resp = curl_requests.post(
        GQL_URL,
        json={"query": query, "variables": variables or {}},
        headers=HEADERS,
        impersonate="chrome124",
        timeout=15,
    )
    return resp.json()

# Step 1: Find Markdown type fields
print("=== Markdown type ===")
r = gql('{ __type(name: "Markdown") { fields { name type { name kind ofType { name } } } } }')
if r.get("data", {}).get("__type"):
    for f in r["data"]["__type"]["fields"]:
        print(f"  {f['name']}: {f['type']}")

# Step 2: Find ParentsGuide type fields (for severity)
print("\n=== ParentsGuide type ===")
r = gql('{ __type(name: "ParentsGuide") { fields { name type { name kind ofType { name kind ofType { name } } } } } }')
if r.get("data", {}).get("__type"):
    for f in r["data"]["__type"]["fields"]:
        print(f"  {f['name']}: {f['type']}")

# Step 3: Find ParentsGuideCategory type (for severity levels)
print("\n=== ParentsGuideCategory type ===")
r = gql('{ __type(name: "ParentsGuideCategory") { fields { name type { name kind ofType { name kind } } } } }')
if r.get("data", {}).get("__type"):
    for f in r["data"]["__type"]["fields"]:
        print(f"  {f['name']}: {f['type']}")

# Step 4: Full query with text
print("\n=== Full query with text ===")
r = gql("""
query {
  title(id: "tt7131622") {
    titleText { text }
    parentsGuide {
      guideItems(first: 50) {
        edges {
          node {
            id
            isSpoiler
            category { id text }
            text { plainText }
          }
        }
      }
    }
  }
}
""")
if "errors" in r:
    print(f"  Error: {json.dumps(r['errors'], indent=2)[:500]}")
else:
    items = r.get("data", {}).get("title", {}).get("parentsGuide", {}).get("guideItems", {}).get("edges", [])
    print(f"  Got {len(items)} items")
    for edge in items[:5]:
        node = edge["node"]
        cat = node["category"]["text"]
        text = node.get("text", {}).get("plainText", "N/A")
        print(f"  [{cat}] {text[:120]}")
