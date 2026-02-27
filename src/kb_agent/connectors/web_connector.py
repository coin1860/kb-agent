"""
Web connector — fetch a URL, extract meaningful content, convert to Markdown.

Supports two backends (selectable via KB_AGENT_WEB_ENGINE env var / /web_load):
  - "markdownify"  (default) — requests + BeautifulSoup + markdownify. Lightweight.
  - "crawl4ai"               — Playwright-based. Handles JS-rendered pages.
"""

import asyncio
import hashlib
import logging
import os
import re
from typing import List, Dict, Any
from urllib.parse import urlparse

from .base import BaseConnector

logger = logging.getLogger("kb_agent_audit")


def _get_web_engine() -> str:
    """Return the configured web engine name (default: 'markdownify')."""
    return os.getenv("KB_AGENT_WEB_ENGINE", "markdownify").lower().strip()


class WebConnector(BaseConnector):
    """Fetches a web page, extracts meaningful text, and returns Markdown.

    Backend is selected by KB_AGENT_WEB_ENGINE env var:
      - "markdownify" (default): lightweight, no browser dependency.
      - "crawl4ai": full browser rendering via Playwright.
    """

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

        Backend is chosen by KB_AGENT_WEB_ENGINE (default: markdownify).

        Args:
            query: The URL to fetch.

        Returns:
            List with one dict: {id, title, content (markdown), metadata}.
        """
        url = query.strip()
        
        # Defensive check: if it has spaces, it's definitely a search query, not a URL
        if " " in url or "\n" in url:
            return [{
                "id": "invalid_url",
                "title": "Invalid URL Error",
                "content": f"Error: '{query}' is not a valid URL. The web_fetch tool ONLY accepts valid HTTP/HTTPS URLs (like 'https://example.com'). It CANNOT be used for web searches.",
                "metadata": {"source": "web", "error": True}
            }]

        if not url.startswith(("http://", "https://")):
            url = "https://" + url

        engine = _get_web_engine()
        logger.info(f"web_fetch engine={engine} url={url}")

        if engine == "crawl4ai":
            try:
                return self._fetch_with_crawl4ai(url)
            except Exception as e:
                logger.warning(f"Crawl4AI failed for {url}: {e}. Falling back to markdownify.")
                return self._fetch_with_requests(url)
        else:
            # Default: markdownify (requests + bs4 + markdownify)
            return self._fetch_with_requests(url)

    def _fetch_with_crawl4ai(self, url: str) -> List[Dict[str, Any]]:
        """Use Crawl4AI for high-quality HTML→Markdown conversion."""
        from crawl4ai import AsyncWebCrawler, BrowserConfig, CrawlerRunConfig, CacheMode
        from crawl4ai.content_filter_strategy import PruningContentFilter
        from crawl4ai.markdown_generation_strategy import DefaultMarkdownGenerator

        async def _crawl():
            browser_config = BrowserConfig(
                headless=True,
                verbose=False,
            )

            md_generator = DefaultMarkdownGenerator(
                content_filter=PruningContentFilter(
                    threshold=0.4,
                    threshold_type="fixed",
                )
            )

            run_config = CrawlerRunConfig(
                cache_mode=CacheMode.BYPASS,
                markdown_generator=md_generator,
            )

            async with AsyncWebCrawler(config=browser_config) as crawler:
                result = await crawler.arun(url=url, config=run_config)
                return result

        # Run the async crawl in a sync context
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            loop = None

        if loop and loop.is_running():
            # We're inside an existing event loop (e.g. LangGraph) —
            # run in a separate thread to avoid blocking
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor() as pool:
                result = pool.submit(lambda: asyncio.run(_crawl())).result(timeout=30)
        else:
            result = asyncio.run(_crawl())

        if not result.success:
            raise RuntimeError(f"Crawl4AI crawl failed: {result.error_message}")

        # Use fit_markdown (filtered) if available, fall back to raw_markdown
        markdown_obj = result.markdown
        if hasattr(markdown_obj, 'fit_markdown') and markdown_obj.fit_markdown:
            markdown = markdown_obj.fit_markdown
        elif hasattr(markdown_obj, 'raw_markdown') and markdown_obj.raw_markdown:
            markdown = markdown_obj.raw_markdown
        elif isinstance(markdown_obj, str):
            markdown = markdown_obj
        else:
            markdown = str(markdown_obj)

        # Clean up
        markdown = re.sub(r"\n{3,}", "\n\n", markdown).strip()

        # Extract title
        title = ""
        if result.metadata and isinstance(result.metadata, dict):
            title = result.metadata.get("title", "")
        if not title:
            # Try to get from first heading
            heading_match = re.match(r"#\s+(.+)", markdown)
            if heading_match:
                title = heading_match.group(1).strip()

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
                "method": "crawl4ai",
            },
        }]

    def _fetch_with_requests(self, url: str) -> List[Dict[str, Any]]:
        """Fallback: use requests + beautifulsoup + markdownify."""
        import requests
        from bs4 import BeautifulSoup
        from markdownify import markdownify as md

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

        title = ""
        if soup.title and soup.title.string:
            title = soup.title.string.strip()

        # Remove non-content elements
        for tag_name in ["script", "style", "nav", "footer", "header", "aside",
                         "form", "button", "iframe", "noscript", "svg"]:
            for tag in soup.find_all(tag_name):
                tag.decompose()

        for selector in ["[class*='cookie']", "[class*='banner']", "[class*='popup']",
                         "[class*='modal']", "[class*='sidebar']", "[class*='advertisement']",
                         "[class*='social']", "[id*='cookie']", "[id*='banner']"]:
            for el in soup.select(selector):
                el.decompose()

        main_content = (
            soup.find("article")
            or soup.find("main")
            or soup.find("div", {"role": "main"})
            or soup.find("div", class_=re.compile(r"(content|article|post|entry)", re.I))
            or soup.body
        )
        if main_content is None:
            main_content = soup

        markdown = md(str(main_content), heading_style="ATX", bullets="-", strip=["img"])
        markdown = re.sub(r"\n{3,}", "\n\n", markdown).strip()

        if not markdown:
            markdown = f"(No meaningful content extracted from {url})"

        return [{
            "id": self._url_id(url),
            "title": title or url,
            "content": markdown,
            "metadata": {
                "source": "web",
                "url": url,
                "domain": urlparse(url).netloc,
                "method": "requests_fallback",
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
