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
_local_qa: object | None = None
_csv_qa: object | None = None


def reset_tools_cache():
    """Clear the cached tool instances so they pick up new settings on next use."""
    global _grep, _vector, _file, _graph, _jira, _confluence, _web, _local_qa, _csv_qa
    _grep = _vector = _file = _graph = _jira = _confluence = _web = _local_qa = _csv_qa = None


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

def _get_local_qa():
    global _local_qa
    if _local_qa is None:
        from kb_agent.tools.local_file_qa import LocalFileQATool
        _local_qa = LocalFileQATool()
    return _local_qa


def _get_csv_qa():
    global _csv_qa
    if _csv_qa is None:
        import kb_agent.tools.csv_qa_tool as csv_tool
        _csv_qa = csv_tool
    return _csv_qa


def reset_singletons():
    """Reset all lazy singletons — useful for tests."""
    global _grep, _vector, _file, _graph, _jira, _confluence, _web, _local_qa, _csv_qa
    _grep = _vector = _file = _graph = _jira = _confluence = _web = _local_qa = _csv_qa = None


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
    from kb_agent.config import settings
    
    # If reranker is enabled, retrieve more chunks to give the reranker a wider pool
    fetch_k = 20 if settings and settings.use_reranker else 5
    
    results = _get_vector().search(query, n_results=fetch_k)
    if not results:
        return json.dumps({
            "status": "no_results",
            "message": "No relevant documents found for query"
        }, ensure_ascii=False)
        
    # Return all fetched results, rerank_node will filter them down if enabled
    return json.dumps(results[:fetch_k], ensure_ascii=False)


@tool
def read_file(file_path: str, start_line: int = None, end_line: int = None) -> str:
    """Read the full content of a document file by its path, or a specific line range.

    Use this after grep_search or vector_search identifies a relevant file
    and you need the complete content for context. Provide start_line and end_line
    to read only a specific section.

    Args:
        file_path: Path to the file to read (relative or absolute).
        start_line: Optional starting line number (1-indexed).
        end_line: Optional ending line number (inclusive).

    Returns:
        The file content as a string, or a descriptive error message.
    """
    content = _get_file().read_file(file_path, start_line, end_line)
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
    if not results:
        return json.dumps({
            "status": "no_results",
            "tool": "graph_related",
            "message": f"No related entities found for '{entity_id}'."
        }, ensure_ascii=False)
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
def jira_jql(query: str) -> str:
    """Search Jira issues using natural language. The query will be
    converted to JQL automatically.

    Use this when the user wants to search Jira based on criteria like
    "my unresolved tasks", "high priority bugs in project X",
    "issues assigned to me updated this week", etc.

    Args:
        query: Natural language description of the Jira search criteria.

    Returns:
        JSON array of matching Jira issues with details.
    """
    results = _get_jira().jql_search(query)
    return json.dumps(results, ensure_ascii=False)


@tool
def confluence_fetch(page_id: str) -> str:
    """Fetch a Confluence page by its numeric ID or search for pages by text.

    Use this tool when:
    - The user mentions a Confluence page ID (a 5+ digit number like 132123, 456789)
    - The user says "confluence" followed by a number
    - The user provides a bare numeric ID and asks to read/summarize/explain it
    - You discover a linked page via the Knowledge Graph

    This is the PRIMARY tool for retrieving Confluence page content.

    Args:
        page_id: Confluence page ID (numeric, e.g. '132123') or search text.

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


@tool
def local_file_qa(filename_prefix: str) -> str:
    """Read a local file by its filename prefix in the datastore to answer Q&A.
    
    Use this when the user provides a specific filename (e.g., '银行开户指南' or 
    from the /file search command) and asks a question about its contents 
    (e.g., "what to prepare for account opening?").

    Args:
        filename_prefix: The exact filename or prefix to search for.

    Returns:
        The text content of the matching file.
    """
    result = _get_local_qa().query(filename_prefix)
    # Detect "not found" error messages and return structured no_results
    if result.startswith("No files found") or result.startswith("Error"):
        return json.dumps({
            "status": "no_results",
            "message": result
        }, ensure_ascii=False)
    return result


@tool
def csv_info(filename: str) -> str:
    """Get the schema and a small sample of a CSV file.

    Use this FIRST before querying any CSV file to understand its structure
    and verify column names.

    Args:
        filename: Name of the CSV file.

    Returns:
        A markdown string containing the schema and a sample of the data.
    """
    return _get_csv_qa().get_csv_schema_and_sample(filename)


@tool
def csv_query(filename: str, query_json_str: str) -> str:
    """Query a CSV file using a structured JSON containing 'condition' and 'columns'.

    CRITICAL INSTRUCTION:
    DO NOT guess the column names. You MUST call the `csv_info` tool first to get 
    the correct headers and schema before you ever use this tool.
    
    Args:
        filename: Name of the CSV file to query (e.g. 'dataset.csv')
        query_json_str: A JSON string with 'condition' (pandas query string) and 'columns' (list of columns).

    Returns:
        Markdown table of the queried results.
    """
    return _get_csv_qa().csv_query(filename, query_json_str)


# Convenience list for graph construction
ALL_TOOLS = [
    # grep_search, # TEMPORARILY DISABLED
    vector_search,
    read_file,
    # graph_related,
    jira_fetch,
    jira_jql,
    confluence_fetch,
    web_fetch,
    local_file_qa,
    csv_info,
    csv_query
]
