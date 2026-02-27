"""
LangChain tool wrappers around existing tool / connector classes.

Each function is decorated with ``@tool`` so LangGraph's ``ToolNode`` (or a
custom tool executor) can call them by name.  The return value is always a
plain string (usually JSON) so the LLM can consume it.
"""

from __future__ import annotations

import json
from typing import Optional

from langchain_core.tools import tool

# ---------------------------------------------------------------------------
# Lazy singletons — created on first call so tests can monkeypatch easily.
# ---------------------------------------------------------------------------

_grep: object | None = None
_vector: object | None = None
_file: object | None = None
_graph: object | None = None
_jira: object | None = None
_confluence: object | None = None
_web: object | None = None


def _get_grep():
    global _grep
    if _grep is None:
        from kb_agent.tools.grep_tool import GrepTool
        _grep = GrepTool()
    return _grep


def _get_vector():
    global _vector
    if _vector is None:
        from kb_agent.tools.vector_tool import VectorTool
        _vector = VectorTool()
    return _vector


def _get_file():
    global _file
    if _file is None:
        from kb_agent.tools.file_tool import FileTool
        _file = FileTool()
    return _file


def _get_graph():
    global _graph
    if _graph is None:
        from kb_agent.tools.graph_tool import GraphTool
        _graph = GraphTool()
    return _graph


def _get_jira():
    global _jira
    if _jira is None:
        from kb_agent.connectors.jira import JiraConnector
        _jira = JiraConnector()
    return _jira


def _get_confluence():
    global _confluence
    if _confluence is None:
        from kb_agent.connectors.confluence import ConfluenceConnector
        _confluence = ConfluenceConnector()
    return _confluence


def _get_web():
    global _web
    if _web is None:
        from kb_agent.connectors.web_connector import WebConnector
        _web = WebConnector()
    return _web


def reset_singletons():
    """Reset all lazy singletons — useful for tests."""
    global _grep, _vector, _file, _graph, _jira, _confluence, _web
    _grep = _vector = _file = _graph = _jira = _confluence = _web = None


# ---------------------------------------------------------------------------
# Tool definitions
# ---------------------------------------------------------------------------


@tool
def grep_search(query: str) -> str:
    """Search indexed Markdown files for an exact keyword match using ripgrep.

    Use this tool FIRST for precise keyword or entity lookups (e.g. ticket IDs,
    exact phrases, config names).

    Args:
        query: The keyword or phrase to search for.

    Returns:
        JSON array of matches with file_path, line number, and content.
    """
    results = _get_grep().search(query)
    return json.dumps(results[:20], ensure_ascii=False)


@tool
def vector_search(query: str) -> str:
    """Semantic similarity search over indexed documents using ChromaDB.

    Use this tool when exact keyword search does not return useful results, or
    when the user's question is conceptual / uses different wording.

    Args:
        query: A natural-language search query.

    Returns:
        JSON array of matches with id, content snippet, metadata, and score.
    """
    results = _get_vector().search(query, n_results=5)
    return json.dumps(results[:10], ensure_ascii=False)


@tool
def read_file(file_path: str) -> str:
    """Read the full content of a document file by its path.

    Use this after grep_search or vector_search identifies a relevant file
    and you need the complete content for context.

    Args:
        file_path: Path to the file to read (relative or absolute).

    Returns:
        The file content as a string, or an error message.
    """
    content = _get_file().read_file(file_path)
    if content is None:
        return f"File not found or access denied: {file_path}"
    if len(content) > 8000:
        return content[:8000] + "\n... (truncated)"
    return content


@tool
def graph_related(entity_id: str) -> str:
    """Find related entities in the Knowledge Graph.

    Use this to navigate relationships between Jira tickets, Confluence pages,
    and documentation files (e.g. find parent ticket, linked pages).

    Args:
        entity_id: The entity identifier (e.g. 'PROJ-123' or 'document.md').

    Returns:
        JSON array of related nodes with node id, type, relation, and direction.
    """
    results = _get_graph().get_related_nodes(entity_id)
    return json.dumps(results[:20], ensure_ascii=False)


@tool
def jira_fetch(issue_key: str) -> str:
    """Fetch a Jira issue by its key (e.g. PROJ-123) or search Jira with text.

    Use this when the user asks about a specific Jira ticket or wants to search
    for issues. Supports both issue key lookup and JQL text search.

    Args:
        issue_key: The Jira issue key (e.g. 'PROJ-123') or search text.

    Returns:
        JSON with id, title, content, and metadata of the issue(s).
    """
    results = _get_jira().fetch_data(issue_key)
    return json.dumps(results, ensure_ascii=False)


@tool
def confluence_fetch(page_id: str) -> str:
    """Fetch a Confluence page by its ID or search for pages by text.

    Use this when the user mentions a Confluence page or you discover a
    linked page via the Knowledge Graph.

    Args:
        page_id: Confluence page ID (numeric) or search text.

    Returns:
        JSON with id, title, content, and metadata of the page(s).
    """
    results = _get_confluence().fetch_data(page_id)
    return json.dumps(results, ensure_ascii=False)


@tool
def web_fetch(url: str) -> str:
    """Fetch a web page by URL and convert its content to Markdown.

    Use this ONLY when you have a specific, valid HTTP/HTTPS URL. Do NOT pass 
    natural language search queries (like "who is shane") into this tool. The 
    tool expects strictly formatted URLs (e.g. 'https://example.com').

    Args:
        url: The absolute HTTP/HTTPS URL to fetch.

    Returns:
        JSON with id, title, content (markdown), and metadata.
    """
    results = _get_web().fetch_data(url)
    for r in results:
        if len(r.get("content", "")) > 8000:
            r["content"] = r["content"][:8000] + "\n\n... (truncated to save tokens)"
    return json.dumps(results, ensure_ascii=False)


# Convenience list for graph construction
ALL_TOOLS = [
    grep_search,
    vector_search,
    read_file,
    graph_related,
    jira_fetch,
    confluence_fetch,
    web_fetch,
]
