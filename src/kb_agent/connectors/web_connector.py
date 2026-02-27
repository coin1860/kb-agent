"""
Web connector — fetch a URL, extract meaningful content, convert to Markdown.
Follows the same BaseConnector pattern as confluence/jira/local_file connectors.
"""
import hashlib
import re
from typing import List, Dict, Any
from urllib.parse import urlparse

import requests
from bs4 import BeautifulSoup
from markdownify import markdownify as md

from .base import BaseConnector


# Tags that don't carry meaningful content
_REMOVE_TAGS = [
    "script", "style", "nav", "footer", "header", "aside",
    "form", "button", "iframe", "noscript", "svg",
    "figure", "figcaption",
]

# CSS selectors for common ad / cookie / popup wrappers
_REMOVE_SELECTORS = [
    "[class*='cookie']", "[class*='banner']", "[class*='popup']",
    "[class*='modal']", "[class*='sidebar']", "[class*='advertisement']",
    "[class*='social']", "[id*='cookie']", "[id*='banner']", "[id*='popup']",
]


class WebConnector(BaseConnector):
    """Fetches a web page, extracts meaningful text, and returns Markdown."""

    HEADERS = {
        "User-Agent": (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/120.0.0.0 Safari/537.36"
        ),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9,zh-CN;q=0.8",
    }

    def fetch_data(self, query: str) -> List[Dict[str, Any]]:
        """
        Fetch a URL and convert its main content to Markdown.

        Args:
            query: The URL to fetch.

        Returns:
            List with one dict: {id, title, content (markdown), metadata}.
        """
        url = query.strip()
        if not url.startswith(("http://", "https://")):
            url = "https://" + url

        try:
            resp = requests.get(url, headers=self.HEADERS, timeout=15, allow_redirects=True)
            resp.raise_for_status()
            resp.encoding = resp.apparent_encoding or "utf-8"
        except requests.RequestException as e:
            return [{
                "id": self._url_id(url),
                "title": url,
                "content": f"Error fetching URL: {e}",
                "metadata": {"source": "web", "url": url, "error": str(e)},
            }]

        html = resp.text
        soup = BeautifulSoup(html, "html.parser")

        # Extract title
        title = ""
        if soup.title and soup.title.string:
            title = soup.title.string.strip()

        # Remove non-content elements
        for tag_name in _REMOVE_TAGS:
            for tag in soup.find_all(tag_name):
                tag.decompose()

        for selector in _REMOVE_SELECTORS:
            for el in soup.select(selector):
                el.decompose()

        # Try to find the main content container
        main_content = (
            soup.find("article")
            or soup.find("main")
            or soup.find("div", {"role": "main"})
            or soup.find("div", class_=re.compile(r"(content|article|post|entry)", re.I))
            or soup.body
        )

        if main_content is None:
            main_content = soup

        # Convert HTML to Markdown
        markdown = md(
            str(main_content),
            heading_style="ATX",
            bullets="-",
            strip=["img"],  # strip images to keep text only
        )

        # Clean up excessive whitespace
        markdown = re.sub(r"\n{3,}", "\n\n", markdown)
        markdown = markdown.strip()

        if not markdown:
            markdown = f"(No meaningful content extracted from {url})"

        doc_id = self._url_id(url)

        return [{
            "id": doc_id,
            "title": title or url,
            "content": markdown,
            "metadata": {
                "source": "web",
                "url": url,
                "domain": urlparse(url).netloc,
            },
        }]

    def fetch_all(self) -> List[Dict[str, Any]]:
        """Not applicable for web URLs."""
        return []

    @staticmethod
    def _url_id(url: str) -> str:
        """Generate a short deterministic ID from a URL."""
        h = hashlib.md5(url.encode()).hexdigest()[:10]
        domain = urlparse(url).netloc.replace(".", "_")
        return f"web_{domain}_{h}"
