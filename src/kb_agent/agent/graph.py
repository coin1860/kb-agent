"""
LangGraph workflow definition for the agentic RAG pipeline.

Topology:
START → unified_router ─┬─ direct ────────────────────────┐
                        └─ search → plan                  │
                                     │                    │
                     ┌───────────────┘                    │
                     ▼                                    │
                 tool_exec ──────────────────────────────┤
                     │                                    │
                     └──────────────→ grade_evidence      │
                                           ├─ GENERATE ─→ synthesize → END
                                           ├─ REFINE ───→ plan (loop)
                                           └─ RE_RETRIEVE → plan (loop)
"""

from __future__ import annotations

import os
from langgraph.graph import StateGraph, END

from .state import AgentState
from .nodes import (
    unified_router_node,
    plan_node,
    tool_node,
    rerank_node,
    grade_evidence_node,
    reflect_node,
    synthesize_node
)


def _route_after_reflect(state: AgentState) -> str:
    """Conditional edge after reflect_node extraction."""
    verdict = state.get("reflection_verdict", "sufficient")
    
    if verdict == "sufficient":
        return "synthesize"
    if verdict == "exhausted":
        return "synthesize"
    if verdict == "needs_precision":
        return "plan"
        
    return "synthesize"


def _route_after_tool_exec(state: AgentState) -> str:
    """Conditional edge after tool_exec: skip grading for simple queries."""
    return "grade_evidence"


def _route_after_router(state: AgentState) -> str:
    """Conditional edge after unified_router: bypass search for direct answers."""
    if state.get("route_decision") == "direct":
        return "synthesize"
    return "plan"


def build_graph() -> StateGraph:
    """Construct (but do not compile) the agentic RAG graph."""
    graph = StateGraph(AgentState)

    # Add nodes
    graph.add_node("unified_router", unified_router_node)
    graph.add_node("plan", plan_node)
    graph.add_node("tool_exec", tool_node)
    graph.add_node("rerank_node", rerank_node)
    graph.add_node("grade_evidence", grade_evidence_node)
    graph.add_node("reflect_node", reflect_node)
    graph.add_node("synthesize", synthesize_node)

    # Edges
    graph.set_entry_point("unified_router")
    graph.add_conditional_edges("unified_router", _route_after_router)
    graph.add_edge("plan", "tool_exec")
    graph.add_edge("tool_exec", "rerank_node")
    graph.add_edge("rerank_node", "grade_evidence")
    graph.add_edge("grade_evidence", "reflect_node")
    graph.add_conditional_edges("reflect_node", _route_after_reflect)
    graph.add_edge("synthesize", END)

    return graph


def compile_graph():
    """Build and compile the graph, ready to ``.invoke()``."""
    return build_graph().compile()
