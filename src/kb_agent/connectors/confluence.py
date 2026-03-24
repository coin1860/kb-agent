"""
Connector for fetching Confluence pages via the REST API.

Authentication: Basic auth using email + API token (Atlassian Cloud)
                or Personal Access Token (Confluence Server/Data Center).
"""

import logging
from typing import List, Dict, Any, Optional, Generator
from markdownify import markdownify as md
from atlassian import Confluence

from .base import BaseConnector
import kb_agent.config as config
from kb_agent.connectors.cache import APICache

logger = logging.getLogger("kb_agent_audit")


class ConfluenceConnector(BaseConnector):
    """Fetches Confluence pages using the atlassian-python-api Confluence client."""

    def __init__(self, base_url: str = None, token: str = None):
        settings = config.settings

        self.base_url = base_url
        self.token = token

        if settings:
            if not self.base_url and settings.confluence_url:
                self.base_url = str(settings.confluence_url).rstrip("/")
            if not self.token and settings.confluence_token:
                self.token = settings.confluence_token.get_secret_value()
                
        self.confluence = None
        if self._is_configured:
            self.confluence = Confluence(
                url=self.base_url,
                token=self.token,
                verify_ssl=False
            )

    @property
    def _is_configured(self) -> bool:
        return bool(self.base_url and self.token)

    # ------------------------------------------------------------------
    # fetch_data — by page ID or CQL search
    # ------------------------------------------------------------------

    def fetch_data(self, query: str, force_refresh: bool = False) -> List[Dict[str, Any]]:
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
            return self._fetch_page(query.strip(), force_refresh=force_refresh)
        else:
            return self._search_cql(query)

    def _fetch_page(self, page_id: str, force_refresh: bool = False) -> List[Dict[str, Any]]:
        """Fetch a single Confluence page by its numeric ID."""
        if not self.confluence:
            return [{"id": page_id, "title": "Confluence not configured",
                     "content": "Confluence client is not initialized.",
                     "metadata": {"source": "confluence", "error": True}}]

        cache = APICache()
        if not force_refresh:
            cached = cache.read("confluence", page_id)
            if cached:
                return [cached]

        try:
            page_data = self.confluence.get_page_by_id(
                page_id,
                expand="body.storage,space,version,ancestors"
            )
            
            if not page_data:
                 return [{"id": page_id, "title": f"Page {page_id} not found",
                          "content": f"Confluence page ID {page_id} does not exist or access is denied.",
                          "metadata": {"source": "confluence", "error": True}}]
                          
            formatted_page = self._format_page(page_data)
            cache.write("confluence", page_id, formatted_page)
                          
            return [formatted_page]

        except Exception as e:
            logger.error(f"Confluence API error for page {page_id}: {e}")
            return [{"id": page_id, "title": "Confluence API error",
                     "content": f"Failed to fetch page {page_id}: {e}",
                     "metadata": {"source": "confluence", "error": True}}]

    def get_page(self, page_id: str, force_refresh: bool = False) -> Optional[Dict[str, Any]]:
        """Fetch a single Confluence page by its numeric ID and return formatted dict (including errors)."""
        results = self._fetch_page(page_id, force_refresh=force_refresh)
        return results[0] if results else None

    def _search_cql(self, text: str) -> List[Dict[str, Any]]:
        """Search Confluence using CQL text search."""
        try:
            cql = f'text ~ "{text}" ORDER BY lastmodified DESC'
            # Note: atlassian-python-api does not have a direct direct cql method in its main class, 
            # we can use get method or cql search if available.
            # Alternatively, we can use the rest api explicitly. But wait, atlassian-python-api Confluence
            # has `cql` method as of recent versions.
            
            data = getattr(self.confluence, "cql", lambda cql, **kwargs: 
                self.confluence.get("rest/api/content/search", params={"cql": cql, **kwargs})
            )(cql, limit=5, expand="body.storage,space,version")

            results = []
            for page in data.get("results", []):
                results.append(self._format_page(page))
                
            return results if results else [{
                "id": "search",
                "title": f"No Confluence results for: {text}",
                "content": f"CQL search returned 0 results for '{text}'.",
                "metadata": {"source": "confluence"},
            }]

        except Exception as e:
            logger.error(f"Confluence search error: {e}")
            return [{"id": "search_error", "title": "Confluence search error",
                     "content": f"Failed to search Confluence: {e}",
                     "metadata": {"source": "confluence", "error": True}}]

    # ------------------------------------------------------------------
    # crawl_tree - BFS traversal
    # ------------------------------------------------------------------

    def crawl_tree(self, root_page_id: str, max_depth: int = 3, on_progress=None) -> Generator[Dict[str, Any], None, None]:
        """BFS crawl of a Confluence page tree."""
        if not self._is_configured:
            raise ValueError("Confluence connector is not configured.")
            
        queue = [(root_page_id, 0)]  # (page_id, current_depth)
        visited = set()
        total_found = 0
        
        while queue:
            page_id, depth = queue.pop(0)
            if page_id in visited or depth > max_depth:
                continue
            visited.add(page_id)
            
            try:
                # Fetch page content
                page_data = self.confluence.get_page_by_id(
                    page_id,
                    expand="body.storage,space,version,ancestors"
                )
                formatted_page = self._format_page(page_data)
                
                yield formatted_page
                total_found += 1
                
                if on_progress:
                    on_progress(total_found, formatted_page.get("title", "Unknown"))
                    
                # Get children if not at max depth
                if depth < max_depth:
                    children = self.confluence.get_child_pages(page_id)
                    for child in children:
                        if child['id'] not in visited:
                            queue.append((child['id'], depth + 1))
                            
            except Exception as e:
                logger.error(f"Failed to crawl Confluence page {page_id}: {e}")

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def create_page(self, parent_id: str, title: str, content: str) -> Dict[str, Any]:
        """
        Create a new Confluence page as a child of parent_id.
        
        Args:
            parent_id: The numeric ID of the parent page.
            title: The title of the new page.
            content: The Markdown content for the page (will be converted to HTML storage format).
        """
        if not self.confluence:
            return {"id": "error", "title": "Confluence not configured",
                    "content": "Confluence client is not initialized.",
                    "metadata": {"source": "confluence", "error": True}}

        try:
            # atlassian-python-api create_page expects:
            # space, title, body, parent_id=None, type='page', representation='storage'
            
            # 1. Get parent space key
            parent_page = self.confluence.get_page_by_id(parent_id, expand="space")
            if not parent_page:
                return {"id": "error", "title": "Parent not found",
                        "content": f"Parent page ID {parent_id} does not exist.",
                        "metadata": {"source": "confluence", "error": True}}
            
            space_key = parent_page.get("space", {}).get("key")
            if not space_key:
                return {"id": "error", "title": "Space error",
                        "content": f"Could not determine space for parent page {parent_id}.",
                        "metadata": {"source": "confluence", "error": True}}

            # 2. Create the page
            # Note: atlassian-python-api takes care of storage format if we just pass a string?
            # Actually, we should probably ensure it's wrapped or at least plain.
            # But wait, it converts markdown? No, we should convert MD to HTML if we want it to look good.
            # However, for now, we just pass the content.
            
            new_page = self.confluence.create_page(
                space=space_key,
                title=title,
                body=content,
                parent_id=parent_id,
                type='page',
                representation='storage'
            )
            
            if not new_page:
                return {"id": "error", "title": "Creation failed",
                        "content": "Confluence API returned no data after create_page.",
                        "metadata": {"source": "confluence", "error": True}}
            
            return self._format_page(new_page)

        except Exception as e:
            logger.error(f"Confluence create_page error: {e}")
            return {"id": "error", "title": "Confluence API error",
                     "content": f"Failed to create page: {e}",
                     "metadata": {"source": "confluence", "error": True}}

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

        # Build page URL
        page_url = ""
        if self.base_url:
            web_link = data.get("_links", {}).get("webui", "")
            if web_link:
                page_url = f"{self.base_url}/wiki{web_link}"

        # Build rich content
        content_parts = [
            f"# {title}",
            "",
            f"**Space:** {space.get('name', space.get('key', 'Unknown'))}",
            f"**Version:** {version.get('number', 'Unknown')}",
            f"**Last Modified:** {version.get('when', 'Unknown')} by {version.get('by', {}).get('displayName', 'Unknown')}",
            f"**URL:** {page_url}",
        ]
        if ancestor_titles:
            content_parts.append(f"**Path:** {' > '.join(ancestor_titles)} > {title}")
        content_parts.append("")
        content_parts.append("## Content")
        content_parts.append(content_md)

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
