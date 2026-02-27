"""
Connector for fetching Confluence pages via the REST API.

Authentication: Basic auth using email + API token (Atlassian Cloud)
                or Personal Access Token (Confluence Server/Data Center).
"""

import logging
import requests
from typing import List, Dict, Any, Optional
from markdownify import markdownify as md

from .base import BaseConnector
import kb_agent.config as config

logger = logging.getLogger("kb_agent_audit")


class ConfluenceConnector(BaseConnector):
    """Fetches Confluence pages using the Confluence REST API."""

    def __init__(self, base_url: str = None, email: str = None, token: str = None):
        settings = config.settings

        self.base_url = base_url
        self.email = email
        self.token = token

        if settings:
            if not self.base_url and settings.confluence_url:
                self.base_url = str(settings.confluence_url).rstrip("/")
            if not self.email and settings.confluence_email:
                self.email = settings.confluence_email
            if not self.token and settings.confluence_token:
                self.token = settings.confluence_token.get_secret_value()

    @property
    def _is_configured(self) -> bool:
        return bool(self.base_url and self.token)

    def _auth(self):
        """Return requests auth tuple."""
        if self.email:
            return (self.email, self.token)
        return ("", self.token)

    def _headers(self):
        return {
            "Accept": "application/json",
            "Content-Type": "application/json",
        }

    # ------------------------------------------------------------------
    # fetch_data — by page ID or CQL search
    # ------------------------------------------------------------------

    def fetch_data(self, query: str) -> List[Dict[str, Any]]:
        """
        Fetch Confluence data.

        - If query is purely numeric → fetch page by ID.
        - Otherwise → search using CQL text search.
        """
        if not self._is_configured:
            logger.warning("Confluence not configured. Returning empty.")
            return [{"id": query, "title": "Confluence not configured",
                     "content": "Confluence URL or API token is not set. "
                                "Please configure KB_AGENT_CONFLUENCE_URL and KB_AGENT_CONFLUENCE_TOKEN in .env.",
                     "metadata": {"source": "confluence", "error": True}}]

        if query.strip().isdigit():
            return self._fetch_page(query.strip())
        else:
            return self._search_cql(query)

    def _fetch_page(self, page_id: str) -> List[Dict[str, Any]]:
        """Fetch a single Confluence page by its numeric ID."""
        url = f"{self.base_url}/wiki/rest/api/content/{page_id}"
        params = {
            "expand": "body.storage,space,version,ancestors",
        }

        try:
            resp = requests.get(url, auth=self._auth(), headers=self._headers(),
                                params=params, timeout=15, verify=False)
            if resp.status_code == 404:
                return [{"id": page_id, "title": f"Page {page_id} not found",
                         "content": f"Confluence page ID {page_id} does not exist.",
                         "metadata": {"source": "confluence", "error": True}}]

            resp.raise_for_status()
            data = resp.json()
            return [self._format_page(data)]

        except requests.RequestException as e:
            logger.error(f"Confluence API error for page {page_id}: {e}")
            return [{"id": page_id, "title": "Confluence API error",
                     "content": f"Failed to fetch page {page_id}: {e}",
                     "metadata": {"source": "confluence", "error": True}}]

    def _search_cql(self, text: str) -> List[Dict[str, Any]]:
        """Search Confluence using CQL text search."""
        url = f"{self.base_url}/wiki/rest/api/content/search"
        params = {
            "cql": f'text ~ "{text}" ORDER BY lastmodified DESC',
            "limit": 5,
            "expand": "body.storage,space,version",
        }

        try:
            resp = requests.get(url, auth=self._auth(), headers=self._headers(),
                                params=params, timeout=15, verify=False)
            resp.raise_for_status()
            data = resp.json()

            results = []
            for page in data.get("results", []):
                results.append(self._format_page(page))
            return results if results else [{
                "id": "search",
                "title": f"No Confluence results for: {text}",
                "content": f"CQL search returned 0 results for '{text}'.",
                "metadata": {"source": "confluence"},
            }]

        except requests.RequestException as e:
            logger.error(f"Confluence search error: {e}")
            return [{"id": "search_error", "title": "Confluence search error",
                     "content": f"Failed to search Confluence: {e}",
                     "metadata": {"source": "confluence", "error": True}}]

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _format_page(self, data: dict) -> Dict[str, Any]:
        """Format a raw Confluence page JSON to our standard format."""
        body_html = data.get("body", {}).get("storage", {}).get("value", "")
        content_md = md(body_html, strip=["img"]) if body_html else "(No content)"

        space = data.get("space", {})
        version = data.get("version", {})
        ancestors = data.get("ancestors", [])
        ancestor_titles = [a.get("title", "") for a in ancestors] if ancestors else []

        title = data.get("title", "Untitled")
        page_id = data.get("id", "")

        # Build rich content
        content_parts = [
            f"# {title}",
            "",
            f"**Space:** {space.get('name', space.get('key', 'Unknown'))}",
            f"**Version:** {version.get('number', 'Unknown')}",
            f"**Last Modified:** {version.get('when', 'Unknown')} by {version.get('by', {}).get('displayName', 'Unknown')}",
        ]
        if ancestor_titles:
            content_parts.append(f"**Path:** {' > '.join(ancestor_titles)} > {title}")
        content_parts.append("")
        content_parts.append("## Content")
        content_parts.append(content_md)

        # Build page URL
        page_url = ""
        if self.base_url:
            web_link = data.get("_links", {}).get("webui", "")
            if web_link:
                page_url = f"{self.base_url}/wiki{web_link}"

        return {
            "id": page_id,
            "title": title,
            "content": "\n".join(content_parts),
            "metadata": {
                "source": "confluence",
                "space": space.get("key", ""),
                "space_name": space.get("name", ""),
                "version": version.get("number", 0),
                "url": page_url,
                "ancestors": ancestor_titles,
            },
        }

    def fetch_all(self) -> List[Dict[str, Any]]:
        """Not implemented — use fetch_data with CQL search instead."""
        return []
