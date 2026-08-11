"""Test more aggressive anti-WAF bypass strategies."""
from curl_cffi import requests as curl_requests
import time

imdb_id = "tt7131622"
url = f"https://www.imdb.com/title/{imdb_id}/parentalguide"

strategies = [
    ("chrome110", {}),
    ("chrome120", {}),
    ("edge101", {}),
    ("safari15_5", {}),
    ("safari17_0", {}),
]

# Strategy: session-based with cookie warmup
print("=== Strategy A: Session with cookie warmup ===")
try:
    session = curl_requests.Session(impersonate="chrome124")
    # First visit homepage to get cookies
    r1 = session.get("https://www.imdb.com/", timeout=15)
    print(f"  Homepage: status={r1.status_code}, cookies={dict(session.cookies)}")
    time.sleep(1)
    # Then visit parental guide
    r2 = session.get(url, timeout=15)
    print(f"  Parental guide: status={r2.status_code}, len={len(r2.text)}")
    if r2.status_code == 200 and len(r2.text) > 5000:
        print("  SUCCESS!")
    session.close()
except Exception as e:
    print(f"  ERROR: {type(e).__name__}: {e}")

# Try different impersonations
for imp, extra in strategies:
    print(f"\n=== Impersonate: {imp} ===")
    try:
        resp = curl_requests.get(url, impersonate=imp, timeout=15)
        print(f"  Status: {resp.status_code}, Length: {len(resp.text)}")
        if resp.status_code == 200 and len(resp.text) > 5000:
            print("  SUCCESS!")
            break
    except Exception as e:
        print(f"  ERROR: {type(e).__name__}: {e}")

# Strategy B: Try mobile URL
print("\n=== Strategy B: Mobile IMDb ===")
try:
    mobile_url = f"https://m.imdb.com/title/{imdb_id}/parentalguide"
    resp = curl_requests.get(mobile_url, impersonate="chrome124", timeout=15)
    print(f"  Status: {resp.status_code}, Length: {len(resp.text)}")
except Exception as e:
    print(f"  ERROR: {e}")

# Strategy C: Try JSON-LD / Next.js data endpoint
print("\n=== Strategy C: IMDb Suggest API ===")
try:
    suggest_url = f"https://v3.sg.media-imdb.com/suggestion/x/{imdb_id}.json"
    resp = curl_requests.get(suggest_url, impersonate="chrome124", timeout=15)
    print(f"  Status: {resp.status_code}")
    if resp.status_code == 200:
        print(f"  Response: {resp.text[:300]}")
except Exception as e:
    print(f"  ERROR: {e}")

# Strategy D: Try GraphQL endpoint
print("\n=== Strategy D: IMDb GraphQL ===")
try:
    gql_url = "https://graphql.imdb.com/"
    query = """
    query ParentalGuide($id: ID!) {
      title(id: $id) {
        id
        titleText { text }
        parentsGuide {
          guideItems(first: 50) {
            edges {
              node {
                category { id text }
                htmlContent { plainText }
              }
            }
          }
        }
      }
    }
    """
    resp = curl_requests.post(
        gql_url,
        json={"query": query, "variables": {"id": imdb_id}},
        headers={
            "Content-Type": "application/json",
            "x-imdb-client-name": "imdb-web-next-localized",
        },
        impersonate="chrome124",
        timeout=15,
    )
    print(f"  Status: {resp.status_code}")
    print(f"  Response: {resp.text[:500]}")
except Exception as e:
    print(f"  ERROR: {type(e).__name__}: {e}")
