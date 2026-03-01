"""
AgentState — the shared state schema for the LangGraph agentic RAG workflow.

Every node in the graph reads from and writes to fields defined here.
"""

from __future__ import annotations

from typing import Any, TypedDict


class AgentState(TypedDict, total=False):
    """State flowing through each node in the agentic RAG graph."""

    # ── User input ────────────────────────────────────────────────────────
    query: str
    """The current user question."""

    messages: list[dict[str, str]]
    """Full conversation history (multi-turn). Each dict has 'role' and 'content'."""

    mode: str
    """Chat mode: 'knowledge_base' or 'normal'."""

    # ── Routing & Analysis ────────────────────────────────────────────────

    evidence_scores: list[float]
    """Relevance scores (0.0-1.0) for each context item from the grader."""

    grader_action: str
    """Action chosen by the grader: 'GENERATE', 'REFINE', or 'RE_RETRIEVE'."""

    # ── Search / retrieval ────────────────────────────────────────────────
    search_queries: list[str]
    """LLM-generated keyword queries for retrieval tools."""

    context: list[str]
    """Accumulated evidence snippets from tools."""

    tool_history: list[dict[str, Any]]
    """Log of tool invocations: [{tool, input, output}, ...]."""

    files_read: list[str]
    """Paths already read — used to de-duplicate file reads."""

    # ── Planner output (tool calls for next step) ─────────────────────────
    pending_tool_calls: list[dict[str, Any]]
    """Tool calls selected by planner: [{name, args}, ...]. JSON-serializable."""

    # ── Control flow ──────────────────────────────────────────────────────
    iteration: int
    """Current plan→tool→evaluate loop count (capped at 3)."""

    is_sufficient: bool
    """Set by the evaluator: True when gathered context can answer the query."""

    # ── Output ────────────────────────────────────────────────────────────
    final_answer: str
    """The synthesised answer returned to the user."""

    # ── TUI integration ───────────────────────────────────────────────────
    status_callback: Any
    """Optional callback ``(emoji: str, msg: str) -> None`` for TUI progress."""

    # ── Tracking & Stats ──────────────────────────────────────────────────
    llm_call_count: int
    """Number of LLM API calls made during this run."""
    
    llm_prompt_tokens: int
    """Total prompt tokens consumed during this run."""
    
    llm_completion_tokens: int
    """Total completion tokens consumed during this run."""
    
    llm_total_tokens: int
    """Total tokens consumed during this run."""
