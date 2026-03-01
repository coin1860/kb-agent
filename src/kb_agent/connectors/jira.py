"""
Connector for fetching Jira issues via the REST API.

Authentication: Basic auth using email + API token (Atlassian Cloud)
                or Personal Access Token (Jira Server/Data Center).
"""

import logging
import requests
from typing import List, Dict, Any, Optional
from markdownify import markdownify as md

from .base import BaseConnector
import kb_agent.config as config

logger = logging.getLogger("kb_agent_audit")


class JiraConnector(BaseConnector):
    """Fetches Jira issues using the Jira REST API v2."""

    def __init__(self, base_url: str = None, token: str = None):
        settings = config.settings

        self.base_url = base_url
        self.token = token

        if settings:
            if not self.base_url and settings.jira_url:
                self.base_url = str(settings.jira_url).rstrip("/")
            if not self.token and settings.jira_token:
                self.token = settings.jira_token.get_secret_value()

    @property
    def _is_configured(self) -> bool:
        return bool(self.base_url and self.token)

    def _headers(self):
        return {
            "Accept": "application/json",
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.token}",
        }

    # ------------------------------------------------------------------
    # fetch_data — single issue by key, or JQL search
    # ------------------------------------------------------------------

    def fetch_data(self, query: str) -> List[Dict[str, Any]]:
        """
        Fetch Jira data.

        - If query looks like an issue key (e.g. PROJ-123) → fetch that issue.
        - Otherwise → run a JQL text search.
        """
        if not self._is_configured:
            logger.warning("Jira not configured (missing URL/token). Returning empty.")
            return [{"id": query, "title": "Jira not configured",
                     "content": "Jira URL or API token is not set. Please configure KB_AGENT_JIRA_URL and KB_AGENT_JIRA_TOKEN in .env.",
                     "metadata": {"source": "jira", "error": True}}]

        # Detect issue key pattern (e.g. ABC-123)
        import re
        if re.match(r'^[A-Z][A-Z0-9]+-\d+$', query.strip()):
            return self._fetch_issue(query.strip())
        else:
            return self._search_jql(query)

    def _fetch_issue(self, issue_key: str) -> List[Dict[str, Any]]:
        """Fetch a single Jira issue by key."""
        url = f"{self.base_url}/rest/api/2/issue/{issue_key}"
        params = {"expand": "renderedFields"}

        try:
            resp = requests.get(url, headers=self._headers(),
                                params=params, timeout=15, verify=False)
            if resp.status_code == 404:
                return [{"id": issue_key, "title": f"Issue {issue_key} not found",
                         "content": f"Jira issue {issue_key} does not exist.",
                         "metadata": {"source": "jira", "error": True}}]

            resp.raise_for_status()
            data = resp.json()
            return [self._format_issue(data)]

        except requests.RequestException as e:
            logger.error(f"Jira API error for {issue_key}: {e}")
            return [{"id": issue_key, "title": f"Jira API error",
                     "content": f"Failed to fetch {issue_key}: {e}",
                     "metadata": {"source": "jira", "error": True}}]

    def _search_jql(self, text: str) -> List[Dict[str, Any]]:
        """Search Jira using JQL text search."""
        url = f"{self.base_url}/rest/api/2/search"
        jql = f'text ~ "{text}" ORDER BY updated DESC'
        params = {
            "jql": jql,
            "maxResults": 5,
            "fields": "summary,description,status,priority,assignee,reporter,"
                      "issuetype,created,updated,labels,components",
            "expand": "renderedFields",
        }

        try:
            resp = requests.get(url, headers=self._headers(),
                                params=params, timeout=15, verify=False)
            resp.raise_for_status()
            data = resp.json()

            results = []
            for issue in data.get("issues", []):
                results.append(self._format_issue(issue))
            return results if results else [{
                "id": "search",
                "title": f"No Jira results for: {text}",
                "content": f"JQL search '{jql}' returned 0 results.",
                "metadata": {"source": "jira"},
            }]

        except requests.RequestException as e:
            logger.error(f"Jira search error: {e}")
            return [{"id": "search_error", "title": "Jira search error",
                     "content": f"Failed to search Jira: {e}",
                     "metadata": {"source": "jira", "error": True}}]

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _format_issue(self, data: dict) -> Dict[str, Any]:
        """Format a raw Jira issue JSON into our standard format."""
        fields = data.get("fields", {})
        rendered = data.get("renderedFields", {})

        # Prefer rendered (HTML) description, convert to markdown
        description = rendered.get("description") or fields.get("description") or ""
        if "<" in description:  # looks like HTML
            description = md(description, strip=["img"])

        assignee = fields.get("assignee")
        reporter = fields.get("reporter")
        status = fields.get("status", {})
        priority = fields.get("priority", {})
        issuetype = fields.get("issuetype", {})
        components = [c.get("name", "") for c in fields.get("components", [])]
        labels = fields.get("labels", [])

        # Build a rich content string
        content_parts = [
            f"# {data.get('key', '')} — {fields.get('summary', '')}",
            "",
            f"**Type:** {issuetype.get('name', 'Unknown')}",
            f"**Status:** {status.get('name', 'Unknown')}",
            f"**Priority:** {priority.get('name', 'Unknown')}",
            f"**Assignee:** {assignee.get('displayName', 'Unassigned') if assignee else 'Unassigned'}",
            f"**Reporter:** {reporter.get('displayName', 'Unknown') if reporter else 'Unknown'}",
        ]
        if labels:
            content_parts.append(f"**Labels:** {', '.join(labels)}")
        if components:
            content_parts.append(f"**Components:** {', '.join(components)}")
        content_parts.append(f"**Created:** {fields.get('created', '')}")
        content_parts.append(f"**Updated:** {fields.get('updated', '')}")
        content_parts.append("")
        content_parts.append("## Description")
        content_parts.append(description or "(No description)")

        return {
            "id": data.get("key", ""),
            "title": fields.get("summary", ""),
            "content": "\n".join(content_parts),
            "metadata": {
                "source": "jira",
                "status": status.get("name", "Unknown"),
                "priority": priority.get("name", "Unknown"),
                "assignee": assignee.get("displayName", "") if assignee else "",
                "type": issuetype.get("name", ""),
                "labels": labels,
                "url": f"{self.base_url}/browse/{data.get('key', '')}",
            },
        }

    def fetch_all(self) -> List[Dict[str, Any]]:
        """Not implemented — use fetch_data with JQL search instead."""
        return []
