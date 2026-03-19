"""
Connector for fetching Jira issues via the REST API.

Authentication: Basic auth using email + API token (Atlassian Cloud)
                or Personal Access Token (Jira Server/Data Center).
"""

import logging
from typing import List, Dict, Any, Optional
from markdownify import markdownify as md
from atlassian import Jira

from .base import BaseConnector
import kb_agent.config as config

logger = logging.getLogger("kb_agent_audit")


class JiraConnector(BaseConnector):
    """Fetches Jira issues using the atlassian-python-api Jira client."""

    def __init__(self, base_url: str = None, token: str = None):
        settings = config.settings

        self.base_url = base_url
        self.token = token

        if settings:
            if not self.base_url and settings.jira_url:
                self.base_url = str(settings.jira_url).rstrip("/")
            if not self.token and settings.jira_token:
                self.token = settings.jira_token.get_secret_value()
                
        self.jira = None
        if self._is_configured:
            self.jira = Jira(
                url=self.base_url,
                token=self.token,
                verify_ssl=False
            )

    @property
    def _is_configured(self) -> bool:
        return bool(self.base_url and self.token)

    # ------------------------------------------------------------------
    # fetch_data — single issue by key, or text search
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
            return self._search_jql(f'text ~ "{query}" ORDER BY updated DESC')

    def _fetch_issue(self, issue_key: str) -> List[Dict[str, Any]]:
        """Fetch a single Jira issue by key."""
        if not self.jira:
            return [{"id": issue_key, "title": "Jira not configured",
                     "content": "Jira client is not initialized.",
                     "metadata": {"source": "jira", "error": True}}]
        try:
            issue_data = self.jira.issue(issue_key, expand="renderedFields")
            if not issue_data:
                return [{"id": issue_key, "title": f"Issue {issue_key} not found",
                         "content": f"Jira issue {issue_key} does not exist or access is denied.",
                         "metadata": {"source": "jira", "error": True}}]
                         
            return [self._format_issue(issue_data)]

        except Exception as e:
            logger.error(f"Jira API error for {issue_key}: {e}")
            return [{"id": issue_key, "title": f"Jira API error",
                     "content": f"Failed to fetch {issue_key}: {e}",
                     "metadata": {"source": "jira", "error": True}}]

    def get_issue(self, issue_key: str) -> Optional[Dict[str, Any]]:
        """Fetch a single Jira issue by key and return formatted dict (including errors)."""
        results = self._fetch_issue(issue_key)
        return results[0] if results else None

    def _search_jql(self, jql: str) -> List[Dict[str, Any]]:
        """Search Jira using arbitrary JQL query."""
        try:
            data = self.jira.jql(jql, limit=20, expand="renderedFields")
            
            results = []
            for issue in data.get("issues", []):
                results.append(self._format_issue(issue))
                
            return results if results else [{
                "id": "search",
                "title": f"No Jira results",
                "content": f"JQL search '{jql}' returned 0 results.",
                "metadata": {"source": "jira"},
            }]

        except Exception as e:
            logger.error(f"Jira search error: {e}")
            return [{"id": "search_error", "title": "Jira search error",
                     "content": f"Failed to execute JQL '{jql}': {e}",
                     "metadata": {"source": "jira", "error": True}}]

    def jql_search(self, natural_query: str) -> List[Dict[str, Any]]:
        """Use LLM to convert a natural language query to JQL, then execute it."""
        from kb_agent.llm import LLMClient
        import re
        
        if not self._is_configured:
            return [{"id": natural_query, "title": "Jira not configured",
                     "content": "Jira URL or API token is not set.",
                     "metadata": {"source": "jira", "error": True}}]
                     
        jql_prompt = f"""Convert the following natural language query to Jira JQL.
Output ONLY the JQL string, nothing else. Do not use formatting like markdown code blocks.

Available JQL functions: currentUser(), now(), startOfDay(), endOfDay(), 
startOfWeek(), endOfWeek(), startOfMonth(), endOfMonth()

Examples:
- "my unresolved tasks" → assignee = currentUser() AND resolution = Unresolved ORDER BY updated DESC
- "high priority bugs" → priority in (High, Highest) AND type = Bug ORDER BY created DESC
- "tasks updated this week" → updated >= startOfWeek() ORDER BY updated DESC

Query: {natural_query}
JQL:"""
        
        try:
            llm = LLMClient()
            jql = llm.chat_completion([
                {"role": "system", "content": "You are a JQL expert. Output ONLY valid JQL."},
                {"role": "user", "content": jql_prompt}
            ]).strip()
            
            # Remove any markdown code blocks if the LLM adds them despite instructions
            jql = re.sub(r'^```jql\s*', '', jql, flags=re.IGNORECASE)
            jql = re.sub(r'^```\s*', '', jql)
            jql = re.sub(r'\s*```$', '', jql)
            
            logger.info(f"Generated JQL: {jql} from query: {natural_query}")
            return self._search_jql(jql)
            
        except Exception as e:
             logger.error(f"JQL Generation or Execution Error: {e}")
             return [{"id": "search_error", "title": "Jira JQL error",
                      "content": f"Failed to generate or execute JQL: {e}",
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
            
        issue_key = data.get("key", "")
        summary = fields.get("summary", "")
        issue_url = f"{self.base_url}/browse/{issue_key}"

        assignee = fields.get("assignee")
        reporter = fields.get("reporter")
        status = fields.get("status", {})
        priority = fields.get("priority", {})
        issuetype = fields.get("issuetype", {})
        components = [c.get("name", "") for c in fields.get("components", [])]
        labels = fields.get("labels", [])

        # Build a rich content string
        content_parts = [
            f"# {issue_key} — {summary}",
            "",
            f"**Type:** {issuetype.get('name', 'Unknown')} | **Status:** {status.get('name', 'Unknown')} | **Priority:** {priority.get('name', 'Unknown')}",
            f"**Assignee:** {assignee.get('displayName', 'Unassigned') if assignee else 'Unassigned'} | **Reporter:** {reporter.get('displayName', 'Unknown') if reporter else 'Unknown'}",
        ]
        if labels:
            content_parts.append(f"**Labels:** {', '.join(labels)}")
        if components:
            content_parts.append(f"**Components:** {', '.join(components)}")
        content_parts.append(f"**Created:** {fields.get('created', '')} | **Updated:** {fields.get('updated', '')}")
        content_parts.append(f"**URL:** {issue_url}")
        content_parts.append("")
        content_parts.append("## Description")
        content_parts.append(description or "(No description)")
        
        # --- Sub-tasks ---
        subtasks = fields.get("subtasks", [])
        if subtasks:
            content_parts.append("\n## Sub-Tasks")
            content_parts.append("| Key | Summary | Status | Assignee |")
            content_parts.append("|-----|---------|--------|----------|")
            for st in subtasks:
                st_key = st.get("key", "")
                st_summary = st.get("fields", {}).get("summary", "")
                st_status = st.get("fields", {}).get("status", {}).get("name", "")
                st_assignee = st.get("fields", {}).get("assignee", {})
                st_assignee_name = st_assignee.get("displayName", "Unassigned") if st_assignee else "Unassigned"
                link = f"[{st_key}]({self.base_url}/browse/{st_key})"
                content_parts.append(f"| {link} | {st_summary} | {st_status} | {st_assignee_name} |")

        # --- Issue Links ---
        issuelinks = fields.get("issuelinks", [])
        if issuelinks:
            content_parts.append("\n## Related Issues")
            content_parts.append("| Relationship | Key | Summary | Status |")
            content_parts.append("|-------------|-----|---------|--------|")
            for link in issuelinks:
                link_type = link.get("type", {})
                if "outwardIssue" in link:
                    relation = link_type.get("outward", "relates to")
                    linked = link["outwardIssue"]
                elif "inwardIssue" in link:
                    relation = link_type.get("inward", "relates to")
                    linked = link["inwardIssue"]
                else:
                    continue
                lk = linked.get("key", "")
                ls = linked.get("fields", {}).get("summary", "")
                lst = linked.get("fields", {}).get("status", {}).get("name", "")
                md_link = f"[{lk}]({self.base_url}/browse/{lk})"
                content_parts.append(f"| {relation} | {md_link} | {ls} | {lst} |")

        return {
            "id": issue_key,
            "title": summary,
            "content": "\n".join(content_parts),
            "metadata": {
                "source": "jira",
                "status": status.get("name", "Unknown"),
                "priority": priority.get("name", "Unknown"),
                "assignee": assignee.get("displayName", "") if assignee else "",
                "type": issuetype.get("name", ""),
                "labels": labels,
                "url": issue_url,
            },
        }

    def fetch_all(self) -> List[Dict[str, Any]]:
        """Not implemented — use fetch_data with JQL search instead."""
        return []
