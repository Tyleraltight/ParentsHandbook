"""Find the correct IMDb GraphQL schema for parental guide data."""
from curl_cffi import requests as curl_requests
import json

GQL_URL = "https://graphql.imdb.com/"
HEADERS = {
    "Content-Type": "application/json",
    "x-imdb-client-name": "imdb-web-next-localized",
}
imdb_id = "tt7131622"

def gql(query, variables=None):
    resp = curl_requests.post(
        GQL_URL,
        json={"query": query, "variables": variables or {}},
        headers=HEADERS,
        impersonate="chrome124",
        timeout=15,
    )
    return resp.json()

# Step 1: Introspect ParentsGuideItem type
print("=== Introspect ParentsGuideItem ===")
result = gql("""
{
  __type(name: "ParentsGuideItem") {
    name
    fields {
      name
      type { name kind ofType { name kind } }
    }
  }
}
""")
print(json.dumps(result, indent=2)[:3000])

# Step 2: Try a simpler parental guide query
print("\n=== Try parentsGuide query ===")
result2 = gql("""
query {
  title(id: "tt7131622") {
    id
    titleText { text }
    parentsGuide {
      guideItems(first: 50) {
        edges {
          node {
            id
            category { id text }
          }
        }
      }
    }
  }
}
""")
print(json.dumps(result2, indent=2)[:3000])

# Step 3: Try alternate field name patterns
print("\n=== Introspect Title.parentsGuide ===")
result3 = gql("""
{
  __type(name: "Title") {
    fields(includeDeprecated: true) {
      name
      type { name kind ofType { name kind } }
    }
  }
}
""")
# Filter for parental related fields
if "data" in result3 and result3["data"].get("__type"):
    fields = result3["data"]["__type"]["fields"]
    for f in fields:
        name = f["name"].lower()
        if any(kw in name for kw in ["parent", "guide", "advisory", "content"]):
            print(f"  {f['name']}: {f['type']}")
else:
    print(json.dumps(result3, indent=2)[:2000])
