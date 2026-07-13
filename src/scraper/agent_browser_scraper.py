import subprocess
import json
import asyncio
import base64
import re
from typing import Dict

from .base import BaseScraper


class AgentBrowserScraper(BaseScraper):
    """
    Scraper using agent-browser CLI (Chrome/CDP) to bypass IMDb's AWS WAF.
    Executes JavaScript in the rendered browser context to extract structured data.
    """

    # JavaScript injected into the fully-rendered page to extract parental guide data.
    # Returns a JSON-string keyed by the four canonical dimension names.
    _EXTRACT_JS = r"""
(function() {
    var result = {};
    var targets = [
        { key: 'Sex & Nudity',       pattern: /sex|nudity/i },
        { key: 'Violence & Gore',    pattern: /violence|gore/i },
        { key: 'Profanity',          pattern: /profanity|language/i },
        { key: 'Frightening Scenes', pattern: /frightening|intense/i }
    ];

    targets.forEach(function(t) { result[t.key] = []; });

    var headers = document.querySelectorAll('h3, h4, [class*="ipc-title__text"]');
    headers.forEach(function(header) {
        var headerText = header.textContent.trim();
        targets.forEach(function(t) {
            if (t.pattern.test(headerText)) {
                var section = header.closest('section');
                if (section) {
                    var items = section.querySelectorAll('.ipc-html-content-inner-div, .ipl-zebra-list__item, li');
                    var texts = Array.from(items).map(i => i.textContent.trim()).filter(txt => txt.length > 5);
                    if (texts.length > 0) {
                        result[t.key].push(texts.join(' \\n '));
                    } else {
                        result[t.key].push(section.innerText);
                    }
                }
            }
        });
    });
    
    var finalResult = {};
    targets.forEach(function(t) {
        var arr = result[t.key];
        var longest = '';
        arr.forEach(function(str) {
            if (str && str.length > longest.length) longest = str;
        });
        finalResult[t.key] = longest;
    });
    return JSON.stringify(finalResult);
})()
"""

    def _run_nav(self, *args, timeout: int = 60) -> None:
        """
        Run a navigation/wait command (open, wait).
        Discard stdout/stderr — these commands drive the daemon and don't
        produce useful output. We must NOT capture stdout here; doing so
        causes subprocess to block waiting for the daemon pipe to close.
        """
        cmd = "agent-browser " + " ".join(
            f'"{a}"' if " " in str(a) else str(a) for a in args
        )
        subprocess.run(
            cmd,
            shell=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            timeout=timeout,
        )

    def _run_query(self, *args, timeout: int = 30) -> str:
        """
        Run a query command (eval, get) that returns output and exits.
        Captures stdout for parsing.
        """
        cmd = "agent-browser " + " ".join(
            f'"{a}"' if " " in str(a) else str(a) for a in args
        )
        proc = subprocess.run(
            cmd,
            shell=True,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        return proc.stdout.strip()

    def fetch_parental_guide(self, imdb_id: str) -> Dict[str, str]:
        url = f"https://www.imdb.com/title/{imdb_id}/parentalguide"

        print(f"      [AgentBrowser] Opening {url}...")
        self._run_nav("open", url, timeout=30)

        print(f"      [AgentBrowser] Waiting for a few seconds to let React render...")
        import time
        time.sleep(5)

        print(f"      [AgentBrowser] Evaluating extraction JS...")
        js_b64 = base64.b64encode(self._EXTRACT_JS.encode()).decode()
        
        data = {}
        for attempt in range(8):
            raw_output = self._run_query("eval", "-b", js_b64, timeout=30)
            
            json_match = re.search(r'\{.*\}', raw_output, re.DOTALL)
            if json_match:
                try:
                    data = json.loads(json_match.group())
                    if any(len(v) > 0 for v in data.values()):
                        break  # React has rendered parental guide chunks
                except json.JSONDecodeError:
                    pass
            import time
            time.sleep(2)
            
        if not data:
            raise ValueError(f"agent-browser eval returned no JSON or content for {imdb_id}.")

        result = {}
        for dim in ["Sex & Nudity", "Violence & Gore", "Profanity", "Frightening Scenes"]:
            text = data.get(dim, "")
            print(f"      [AgentBrowser] {dim}: {len(text)} chars")
            result[dim] = self._clean_text(text) if text else ""

        return result

    async def async_fetch_parental_guide(self, imdb_id: str) -> Dict[str, str]:
        """Async wrapper: runs blocking subprocess calls in a thread pool."""
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, self.fetch_parental_guide, imdb_id)

    @staticmethod
    def _clean_text(text: str, max_len: int = 2000) -> str:
        """Strip noise and truncate to reduce LLM token consumption."""
        text = re.sub(r'&[a-z]+;', ' ', text)
        text = re.sub(r'\s+', ' ', text).strip()
        if len(text) > max_len:
            text = text[:max_len] + '...'
        return text
