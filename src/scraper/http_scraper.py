import httpx
from bs4 import BeautifulSoup
from typing import Dict
import re
import random
from .base import BaseScraper

class HttpScraper(BaseScraper):
    """
    Lightweight HTTP scraper relying on httpx and BeautifulSoup4.
    """
    def __init__(self):
        self.user_agents = [
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.3 Safari/605.1.15",
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:123.0) Gecko/20100101 Firefox/123.0",
            "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
        ]

    def fetch_parental_guide(self, imdb_id: str) -> Dict[str, str]:
        url = f"https://www.imdb.com/title/{imdb_id}/parentalguide"
        headers = {
            "User-Agent": random.choice(self.user_agents),
            "Accept-Language": "en-US,en;q=0.9",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8"
        }
        
        with httpx.Client(follow_redirects=True, timeout=15.0) as client:
            response = client.get(url, headers=headers)
            response.raise_for_status()
            soup = BeautifulSoup(response.text, "html.parser")
            return self._parse_guide_content(soup)

    async def async_fetch_parental_guide(self, imdb_id: str) -> Dict[str, str]:
        """Async version with retry for IMDb 202 anti-scraping responses."""
        import asyncio
        url = f"https://www.imdb.com/title/{imdb_id}/parentalguide"
        max_retries = 3

        for attempt in range(max_retries):
            headers = {
                "User-Agent": random.choice(self.user_agents),
                "Accept-Language": "en-US,en;q=0.9",
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8"
            }
            async with httpx.AsyncClient(follow_redirects=True, timeout=15.0) as client:
                response = await client.get(url, headers=headers)
                # IMDb returns 202 with empty body as anti-scraping; retry
                if response.status_code == 202 or len(response.text) < 100:
                    if attempt < max_retries - 1:
                        await asyncio.sleep(2 * (attempt + 1))
                        continue
                    raise ValueError(f"IMDb returned empty response after {max_retries} retries (status {response.status_code})")
                response.raise_for_status()
                soup = BeautifulSoup(response.text, "html.parser")
                return self._parse_guide_content(soup)

        raise ValueError("IMDb fetch failed: max retries exhausted")

    def _parse_guide_content(self, soup: BeautifulSoup) -> Dict[str, str]:
        dimensions = {
            "Sex & Nudity": "advisory-nudity",
            "Violence & Gore": "advisory-violence",
            "Profanity": "advisory-profanity",
            "Frightening Scenes": "advisory-frightening"
        }
        
        result = {}
        for dim, section_id in dimensions.items():
            # 1. Attempt to find the section wrapper using the classic ID
            section = soup.find(id=section_id)
            
            # 2. If not found, attempt modern Next.js/React structure by finding the header text optionally ignoring trailing words
            if not section:
                # E.g. "Frightening Scenes" on IMDb is now "Frightening & Intense Scenes"
                search_term = dim.split(' ')[0] # "Sex", "Violence", "Profanity", "Frightening"
                header = soup.find(lambda tag: tag.name in ["h4", "h3", "span"] and tag.string and search_term in tag.string)
                
                if header:
                    section = header.find_parent("section") or header.find_parent("div", class_="ipc-page-section")

            text_content = ""
            if section:
                # 3. IMDb description texts might be in classic zebra lists or modern html content divs
                items = section.find_all(class_=["ipl-zebra-list__item", "ipc-html-content-inner-div"])
                if items:
                    text_content = " \n ".join(item.get_text(separator=' ', strip=True) for item in items)
                else:
                    # Fallback to entire section text if specific items are missing
                    text_content = section.get_text(separator=' ', strip=True)
            
            print(f"      [Scraper Debug] {dim} 提取到文本字数: {len(text_content)}")
            
            if len(text_content) == 0:
                raise ValueError(f"严重抓取异常: {dim} 维度的字数为 0。页面结构可能已改变或遇到反爬机制。请检查代理或 User-Agent。")
                
            result[dim] = self._clean_text(text_content)
                
        return result

    @staticmethod
    def _clean_text(text: str, max_len: int = 2000) -> str:
        """Strip noise and truncate to reduce LLM token consumption."""
        # Remove residual HTML entities
        text = re.sub(r'&[a-z]+;', ' ', text)
        # Collapse whitespace
        text = re.sub(r'\s+', ' ', text).strip()
        # Truncate to max length
        if len(text) > max_len:
            text = text[:max_len] + '...'
        return text
