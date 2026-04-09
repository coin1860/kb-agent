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
from kb_agent.connectors.cache import APICache

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

    def fetch_data(self, query: str, force_refresh: bool = False) -> List[Dict[str, Any]]:
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
        if re.match(r'^[A-Z][A-Z0-9]{1,9}-\d{3,5}$', query.strip()):
            return self._fetch_issue(query.strip(), force_refresh=force_refresh)
        else:
            return self._search_jql(f'text ~ "{query}" ORDER BY updated DESC')

    def _fetch_issue(self, issue_key: str, force_refresh: bool = False, inline_depth: int = 0) -> List[Dict[str, Any]]:
        """Fetch a single Jira issue by key."""
        jira_client = self.jira
        if not jira_client:
            return [{"id": issue_key, "title": "Jira not configured",
                     "content": "Jira client is not initialized.",
                     "metadata": {"source": "jira", "error": True}}]

        cache = APICache()
        if not force_refresh:
            cached = cache.read("jira", issue_key)
            if cached:
                return [cached]

        try:
            issue_data = jira_client.issue(issue_key, expand="renderedFields")
            if not issue_data:
                return [{"id": issue_key, "title": f"Issue {issue_key} not found",
                         "content": f"Jira issue {issue_key} does not exist or access is denied.",
                         "metadata": {"source": "jira", "error": True}}]
                         
            comments_data = {}
            try:
                comments_data = jira_client.issue_get_comments(issue_key)
            except Exception as e:
                logger.warning(f"Failed to fetch comments for {issue_key}: {e}")
            comments = comments_data.get("comments", []) if comments_data else []

            formatted_issue = self._format_issue(issue_data, comments=comments)
            
            if inline_depth == 0:
                import re
                description = issue_data.get("renderedFields", {}).get("description") or issue_data.get("fields", {}).get("description") or ""

                # --- Inline Jira Fetching ---
                jira_keys = []
                # 1. From issuelinks (Official priority)
                for link in issue_data.get("fields", {}).get("issuelinks", []):
                    key = None
                    if "outwardIssue" in link:
                        key = link["outwardIssue"].get("key")
                    elif "inwardIssue" in link:
                        key = link["inwardIssue"].get("key")
                    if key and key not in jira_keys:
                        jira_keys.append(key)
                
                # 2. From description (Backup)
                for m in re.finditer(r'[A-Z][A-Z0-9]{1,9}-\d{3,6}', description):
                    key = m.group(0)
                    if key != issue_key and key not in jira_keys:
                        jira_keys.append(key)

                if jira_keys:
                    formatted_issue["content"] += "\n\n## Inline Jira Content"
                    for jk in jira_keys[:3]:
                        try:
                            jk_res = self._fetch_issue(jk, force_refresh=force_refresh, inline_depth=inline_depth + 1)
                            if jk_res and not jk_res[0].get("metadata", {}).get("error"):
                                pc = jk_res[0].get("content", "")
                                title = jk_res[0].get("title", jk)
                                formatted_issue["content"] += f"\n\n### Linked Jira: {jk} - {title}\n{pc}"
                        except Exception as e:
                            logger.warning(f"Failed to fetch Jira {jk}: {e}")

                # --- Inline Confluence Fetching ---
                from kb_agent.connectors.confluence import ConfluenceConnector
                confluence_connector = ConfluenceConnector()
                if confluence_connector._is_configured:
                    page_ids = []
                    
                    # 1. From remote links (prioritized)
                    try:
                        remote_links = jira_client.get_issue_remote_links(issue_key)
                        for rl in remote_links:
                            url = rl.get("object", {}).get("url", "")
                            m1 = re.search(r'pageId=(\d{9,10})', url)
                            m2 = re.search(r'/pages/(\d{9,10})', url)
                            pid = (m1 or m2).group(1) if (m1 or m2) else None
                            if pid and pid not in page_ids:
                                page_ids.append(pid)
                    except Exception as e:
                        logger.warning(f"Failed to fetch remote links for {issue_key}: {e}")

                    # 2. From description mapping
                    for m in re.finditer(r'pageId=(\d{9,10})', description):
                        pid = m.group(1)
                        if pid not in page_ids:
                            page_ids.append(pid)
                    for m in re.finditer(r'/pages/(\d{9,10})', description):
                        pid = m.group(1)
                        if pid not in page_ids:
                            page_ids.append(pid)
                    
                    if page_ids:
                        formatted_issue["content"] += "\n\n## Inline Confluence Content"
                        for pid in page_ids[:3]:  # Limit to 3 Confluence pages to prevent context bloat
                            try:
                                # Fetch page content directly using its ID
                                page_results = confluence_connector.fetch_data(pid, force_refresh=force_refresh)
                                if page_results and not page_results[0].get("metadata", {}).get("error"):
                                    pc = page_results[0].get("content", "")
                                    title = page_results[0].get("title", pid)
                                    formatted_issue["content"] += f"\n\n### Linked Confluence Page: {title}\n{pc}"
                            except Exception as e:
                                logger.warning(f"Failed to fetch Confluence page {pid}: {e}")
            
            # Cache the main issue with all included context
            cache.write("jira", issue_key, formatted_issue)
                    
            return [formatted_issue]

        except Exception as e:
            logger.error(f"Jira API error for {issue_key}: {e}")
            return [{"id": issue_key, "title": f"Jira API error",
                     "content": f"Failed to fetch {issue_key}: {e}",
                     "metadata": {"source": "jira", "error": True}}]

    def get_issue(self, issue_key: str, force_refresh: bool = False) -> Optional[Dict[str, Any]]:
        """Fetch a single Jira issue by key and return formatted dict (including errors)."""
        results = self._fetch_issue(issue_key, force_refresh=force_refresh)
        return results[0] if results else None

    def create_issue(
        self,
        project_key: str,
        summary: str,
        description: str = "",
        issue_type: str = "Task",
    ) -> Dict[str, Any]:
        """
        Create a new Jira issue.

        Args:
            project_key: The Jira project key (e.g. 'KB'). Falls back to
                         settings.jira_default_project if empty.
            summary: The issue title/summary (required).
            description: Optional issue description (plain text).
            issue_type: Issue type name (default: 'Task').

        Returns:
            Dict with 'key', 'url', 'summary', 'project', 'issue_type' on success,
            or 'error': True and 'content': '<message>' on failure.
        """
        if not self._is_configured:
            return {
                "error": True,
                "content": "Jira not configured (missing URL/token). Please set KB_AGENT_JIRA_URL and KB_AGENT_JIRA_TOKEN.",
            }

        # Resolve project key
        resolved_project = project_key.strip() if project_key else ""
        if not resolved_project:
            resolved_project = (config.settings.jira_default_project or "").strip() if config.settings else ""

        if not resolved_project:
            return {
                "error": True,
                "content": (
                    "No project key provided and no default project configured. "
                    "Please specify project_key or set KB_AGENT_JIRA_DEFAULT_PROJECT."
                ),
            }

        if not summary or not summary.strip():
            return {"error": True, "content": "Summary is required to create a Jira issue."}

        try:
            fields: Dict[str, Any] = {
                "project": {"key": resolved_project.upper()},
                "summary": summary.strip(),
                "issuetype": {"name": issue_type},
            }
            if description:
                fields["description"] = description

            result = self.jira.create_issue(fields=fields)

            issue_key = result.get("key", "")
            issue_url = f"{self.base_url}/browse/{issue_key}" if issue_key else ""

            logger.info(f"Created Jira issue: {issue_key}")
            return {
                "key": issue_key,
                "url": issue_url,
                "summary": summary.strip(),
                "project": resolved_project.upper(),
                "issue_type": issue_type,
            }

        except Exception as e:
            logger.error(f"Jira create issue error: {e}")
            return {
                "error": True,
                "content": f"Failed to create Jira issue in project '{resolved_project}': {e}",
            }

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

    def _format_issue(self, data: dict, comments: Optional[List[Dict[str, Any]]] = None) -> Dict[str, Any]:
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
        ]
        if labels:
            content_parts.append(f"**Labels:** {', '.join(labels)}")
        if components:
            content_parts.append(f"**Components:** {', '.join(components)}")
        content_parts.append(f"**URL:** {issue_url}")
        content_parts.append("")
        content_parts.append("## Description")
        content_parts.append(description or "(No description)")
        
        if comments:
            content_parts.append("\n## Comments")
            recent_comments = comments[-10:] # last 10 comments
            for c in reversed(recent_comments):
                author = c.get("author", {}).get("displayName", "Unknown")
                created = c.get("created", "")
                body = c.get("body", "")
                if "<" in body and ">" in body:
                    body = md(body, strip=["img"])
                content_parts.append(f"**From {author} at {created}:**\n{body}\n")

        # --- Extract Confluence links from description ---
        import re
        confluence_links = re.findall(
            r'https?://[^\s\)\]]+/wiki/[^\s\)\]]+|'
            r'https?://[^\s\)\]]+/display/[^\s\)\]]+|'
            r'https?://[^\s\)\]]+/pages/viewpage\.action\?pageId=\d{9,10}',
            description
        )
        if confluence_links:
            content_parts.append("\n## Referenced Confluence Pages")
            seen = set()
            for link in confluence_links:
                if link not in seen:
                    seen.add(link)
            for link in list(seen)[:3]:
                content_parts.append(f"- {link}")
            if len(seen) > 3:
                content_parts.append(f"- (and {len(seen) - 3} more links omitted)")

        # --- Extract Jira links from description ---
        jira_links = re.findall(r'[A-Z][A-Z0-9]{1,9}-\d{3,6}', description)
        jira_links = [k for k in jira_links if k != issue_key]
        if jira_links:
            seen_j = set()
            for link in jira_links:
                if link not in seen_j:
                    seen_j.add(link)
            if seen_j:
                content_parts.append("\n## Referenced Jira Issues")
                for link in list(seen_j)[:3]:
                    content_parts.append(f"- {link}")
                if len(seen_j) > 3:
                    content_parts.append(f"- (and {len(seen_j) - 3} more issues omitted)")
        
        # --- Sub-tasks (NO keys exposed) ---
        subtasks = fields.get("subtasks", [])
        if subtasks:
            content_parts.append("\n<!-- NO_ENTITY_EXTRACT -->")
            content_parts.append(f"## Sub-Tasks ({len(subtasks)} total)")
            for st in subtasks:
                st_summary = st.get("fields", {}).get("summary", "")
                st_status = st.get("fields", {}).get("status", {}).get("name", "")
                content_parts.append(f"- {st_summary} ({st_status})")
            content_parts.append("<!-- /NO_ENTITY_EXTRACT -->")

        # --- Related Issues (no keys in content) ---
        issuelinks = fields.get("issuelinks", [])
        if issuelinks:
            content_parts.append("\n<!-- NO_ENTITY_EXTRACT -->")
            content_parts.append("## Related Issues")
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
                ls = linked.get("fields", {}).get("summary", "")
                lst = linked.get("fields", {}).get("status", {}).get("name", "")
                content_parts.append(f"- {relation}: {ls} ({lst})")
            content_parts.append("<!-- /NO_ENTITY_EXTRACT -->")

        return {
            "id": issue_key,
            "title": summary,
            "content": "\n".join(content_parts),
            "metadata": {
                "source": "jira",
                "status": status.get("name", "Unknown"),
                "priority": priority.get("name", "Unknown"),
                "type": issuetype.get("name", ""),
                "labels": labels,
                "url": issue_url,
                "has_subtasks": bool(subtasks),
                "subtask_count": len(subtasks),
            },
        }

    def fetch_all(self) -> List[Dict[str, Any]]:
        """Not implemented — use fetch_data with JQL search instead."""
        return []
