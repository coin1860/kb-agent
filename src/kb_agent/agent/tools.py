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
from rich.console import Console
from rich.panel import Panel
from rich.text import Text
import kb_agent.config as config

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
def jira_fetch(issue_key: str, force_refresh: bool = False) -> str:
    """Fetch a Jira issue by its key (e.g. PROJ-123) or search Jira with text.

    Use this when the user asks about a specific Jira ticket or wants to search
    for issues. Supports both issue key lookup and JQL text search.

    Args:
        issue_key: The Jira issue key (e.g. 'PROJ-123') or search text.
        force_refresh: If True, bypass the local cache and fetch fresh data from the API. Use when the user explicitly asks to "refresh cache" or "刷新缓存".

    Returns:
        JSON with id, title, content, and metadata of the issue(s).
    """
    results = _get_jira().fetch_data(issue_key, force_refresh=force_refresh)
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
def jira_create_ticket(
    summary: str,
    description: str = "",
    project_key: str = "",
    issue_type: str = "Task",
) -> str:
    """Create a new Jira ticket after confirming with the user.

    Use this when the user wants to create, file, or log a new Jira issue.
    If project_key is not provided, falls back to the configured default project.

    The tool will display a summary of the ticket and ask the user to confirm
    before creating it. No ticket is created without explicit user approval.

    Args:
        summary: The ticket title/summary (required).
        description: Optional detailed description of the issue.
        project_key: Jira project key (e.g. 'KB'). Uses default project if empty.
        issue_type: Issue type (default: 'Task'). Common values: Task, Bug, Story.

    Returns:
        JSON with 'key' and 'url' of the created ticket, or an error/cancel message.
    """
    # Resolve project key
    resolved_project = project_key.strip() if project_key else ""
    if not resolved_project and config.settings:
        resolved_project = (config.settings.jira_default_project or "").strip()

    if not resolved_project:
        return json.dumps({
            "status": "error",
            "message": (
                "No project key provided and no default project configured. "
                "Please specify a project_key argument or set KB_AGENT_JIRA_DEFAULT_PROJECT."
            )
        }, ensure_ascii=False)

    if not summary or not summary.strip():
        return json.dumps({
            "status": "error",
            "message": "Summary is required to create a Jira ticket."
        }, ensure_ascii=False)

    # Display approval panel
    console = Console()
    desc_preview = (description[:120] + "...") if len(description) > 120 else description
    panel_content = Text()
    panel_content.append(f"  Project:      ", style="bold")
    panel_content.append(f"{resolved_project.upper()}\n")
    panel_content.append(f"  Type:         ", style="bold")
    panel_content.append(f"{issue_type}\n")
    panel_content.append(f"  Summary:      ", style="bold")
    panel_content.append(f"{summary.strip()}\n")
    if desc_preview:
        panel_content.append(f"  Description:  ", style="bold")
        panel_content.append(f"{desc_preview}\n")

    console.print()
    console.print(Panel(
        panel_content,
        title="[bold yellow]Create Jira Ticket[/bold yellow]",
        border_style="yellow",
        expand=False,
    ))

    try:
        answer = input("  Create this ticket? [Y/n]: ").strip().lower()
    except (EOFError, KeyboardInterrupt):
        answer = "n"

    if answer not in ("", "y", "yes"):
        return json.dumps({
            "status": "cancelled",
            "message": "Ticket creation cancelled by user."
        }, ensure_ascii=False)

    # Create the ticket
    result = _get_jira().create_issue(
        project_key=resolved_project,
        summary=summary.strip(),
        description=description,
        issue_type=issue_type,
    )
    return json.dumps(result, ensure_ascii=False)


@tool
def confluence_create_page(parent_id: str, title: str, content: str) -> str:
    """Create a new Confluence page as a child of an existing page.

    Use this tool when you need to upload content, create a new document, or 
    add a meeting summary to Confluence.

    Args:
        parent_id: The numeric ID of the parent page (e.g. '123123123').
        title: The title for the new page.
        content: The Markdown content to be uploaded.

    Returns:
        JSON with the details of the newly created page.
    """
    results = _get_confluence().create_page(parent_id, title, content)
    return json.dumps(results, ensure_ascii=False)


@tool
def confluence_fetch(page_id: str, force_refresh: bool = False) -> str:
    """Fetch a Confluence page by its numeric ID or search for pages by text.

    Use this tool when:
    - The user mentions a Confluence page ID (a 5+ digit number like 132123, 456789)
    - The user says "confluence" followed by a number
    - The user provides a bare numeric ID and asks to read/summarize/explain it
    - You discover a linked page via the Knowledge Graph

    This is the PRIMARY tool for retrieving Confluence page content.

    Args:
        page_id: Confluence page ID (numeric, e.g. '132123') or search text.
        force_refresh: If True, bypass the local cache and fetch fresh data from the API. Use when the user explicitly asks to "refresh cache" or "刷新缓存".

    Returns:
        JSON with id, title, content, and metadata of the page(s).
    """
    results = _get_confluence().fetch_data(page_id, force_refresh=force_refresh)
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
def rag_query(query: str) -> str:
    """Run a full RAG (retrieval-augmented generation) pipeline query over the knowledge base.

    Use this tool ONLY when the user explicitly asks to search the knowledge
    base using RAG, e.g. "用RAG查一下...", "search knowledge base for...",
    "RAG查询...". Do NOT use for general questions, coding tasks, or anything
    that does not explicitly mention using RAG.

    Args:
        query: The natural language query to run through the RAG pipeline.

    Returns:
        A synthesized natural language answer from the knowledge base.
    """
    from kb_agent.agent.graph import compile_graph
    graph = compile_graph()
    result_state = graph.invoke({"query": query, "messages": [], "status_callback": None})
    return result_state.get("final_answer") or ""


@tool
def direct_response(answer: str) -> str:
    """Respond directly to the user with a pre-synthesized message.

    Use this tool for greetings (hi, hello), simple pleasantries, chitchat,
    or any query that can be answered directly without searching the 
    knowledge base or local files.

    Args:
        answer: The text message to send to the user.

    Returns:
        The same answer string.
    """
    return answer


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
    jira_create_ticket,
    confluence_fetch,
    confluence_create_page,
    web_fetch,
    local_file_qa,
    csv_info,
    csv_query,
    rag_query,
    direct_response,
]

# NOTE: Cannot set arbitrary attributes on Pydantic StructuredTool objects.
# Instead, use SKILL_TOOL_APPROVAL_REGISTRY to track which tools need approval.
# The registry is keyed by tool.name (the string name of the @tool function).

SKILL_TOOL_APPROVAL_REGISTRY: dict[str, bool] = {}
# All RAG tools default to False; overridden for write_file and run_python when loaded.
for _t in ALL_TOOLS:
    SKILL_TOOL_APPROVAL_REGISTRY[_t.name] = False


def _get_write_file():
    from kb_agent.tools.atomic.file_ops import write_file as _wf
    SKILL_TOOL_APPROVAL_REGISTRY[_wf.name] = True
    return _wf


def _get_run_python():
    from kb_agent.tools.atomic.code_exec import run_python as _rp
    SKILL_TOOL_APPROVAL_REGISTRY[_rp.name] = True
    return _rp


def _get_run_shell():
    from kb_agent.tools.atomic.shell_exec import run_shell as _rs
    SKILL_TOOL_APPROVAL_REGISTRY[_rs.name] = True
    return _rs


def get_skill_tools():
    """Return the full tool list for the skill agent (ALL_TOOLS + atomic write + shell tools)."""
    return ALL_TOOLS + [_get_write_file(), _get_run_python(), _get_run_shell()]


def tool_requires_approval(tool) -> bool:
    """Return True if the given tool requires user approval before execution."""
    return SKILL_TOOL_APPROVAL_REGISTRY.get(getattr(tool, 'name', ''), False)


# Static reference for imports that need the list at module load time
# (lazy so atomic tools don't load unless skill mode is used)
SKILL_TOOLS = None  # Use get_skill_tools() at runtime
