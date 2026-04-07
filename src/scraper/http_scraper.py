import httpx
from typing import Dict
import re
from .base import BaseScraper


class HttpScraper(BaseScraper):
    """
    IMDb parental guide scraper using the public GraphQL API.
    Replaces the old HTML scraper which was blocked by IMDb WAF (202 responses).
    """

    GRAPHQL_URL = "https://graphql.imdb.com/"
    GRAPHQL_HEADERS = {
        "Content-Type": "application/json",
        "x-imdb-client-name": "imdb-web-next-localized",
    }

    # Maps our dimension names to IMDb GraphQL category IDs
    CATEGORY_MAP = {
        "NUDITY":      "Sex & Nudity",
        "VIOLENCE":    "Violence & Gore",
        "PROFANITY":   "Profanity",
        "FRIGHTENING": "Frightening Scenes",
    }

    GRAPHQL_QUERY = """
    query ParentalGuide($id: ID!) {
      title(id: $id) {
        parentsGuide {
          guideItems(first: 100) {
            edges {
              node {
                category { id }
                text { plainText }
                isSpoiler
              }
            }
          }
        }
      }
    }
    """

    def fetch_parental_guide(self, imdb_id: str) -> Dict[str, str]:
        """Sync fetch via GraphQL API."""
        with httpx.Client(timeout=20.0) as client:
            resp = client.post(
                self.GRAPHQL_URL,
                json={"query": self.GRAPHQL_QUERY, "variables": {"id": imdb_id}},
                headers=self.GRAPHQL_HEADERS,
            )
            resp.raise_for_status()
            return self._parse_graphql_response(resp.json(), imdb_id)

    async def async_fetch_parental_guide(self, imdb_id: str) -> Dict[str, str]:
        """Async fetch via GraphQL API."""
        async with httpx.AsyncClient(timeout=20.0) as client:
            resp = await client.post(
                self.GRAPHQL_URL,
                json={"query": self.GRAPHQL_QUERY, "variables": {"id": imdb_id}},
                headers=self.GRAPHQL_HEADERS,
            )
            resp.raise_for_status()
            return self._parse_graphql_response(resp.json(), imdb_id)

    def _parse_graphql_response(self, data: dict, imdb_id: str) -> Dict[str, str]:
        """Parse GraphQL response into {dimension_name: combined_text} dict."""
        # Initialize result with all dimensions
        result: Dict[str, str] = {
            "Sex & Nudity": "",
            "Violence & Gore": "",
            "Profanity": "",
            "Frightening Scenes": "",
        }

        try:
            edges = data["data"]["title"]["parentsGuide"]["guideItems"]["edges"]
        except (KeyError, TypeError):
            print(f"      [Scraper Warning] GraphQL returned unexpected structure for {imdb_id}")
            return result

        # Group items by category
        category_texts: Dict[str, list] = {dim: [] for dim in result}

        for edge in edges:
            node = edge.get("node", {})
            cat_id = node.get("category", {}).get("id", "")
            text = node.get("text", {}).get("plainText", "")

            if cat_id in self.CATEGORY_MAP and text:
                dim_name = self.CATEGORY_MAP[cat_id]
                category_texts[dim_name].append(text)

        # Combine texts per dimension
        for dim, texts in category_texts.items():
            combined = " \n ".join(texts)
            print(f"      [Scraper Debug] {dim} extracted {len(combined)} chars ({len(texts)} items)")
            if not combined:
                print(f"      [Scraper Warning] {dim} returned 0 chars")
            result[dim] = self._clean_text(combined) if combined else ""

        return result

    @staticmethod
    def _clean_text(text: str, max_len: int = 2000) -> str:
        """Strip noise and truncate to reduce LLM token consumption."""
        text = re.sub(r'&[a-z]+;', ' ', text)
        text = re.sub(r'\s+', ' ', text).strip()
        if len(text) > max_len:
            text = text[:max_len] + '...'
        return text
