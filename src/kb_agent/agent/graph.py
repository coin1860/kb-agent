"""
LangGraph workflow definition for the agentic RAG pipeline.

Topology:
START → analyze_and_route ─┬─ chitchat ─────────────────────┐
                           └─ simple/complex → plan        │
                                                │          │
                     ┌──────────────────────────┘          │
                     ▼                                     │
                 tool_exec ── simple ──────────────────────┤
                     │                                     │
                     └─────── complex → grade_evidence     │
                                             ├─ GENERATE ─→ synthesize → END
                                             ├─ REFINE ───→ plan (loop)
                                             └─ RE_RETRIEVE → analyze_and_route (loop)
"""

from __future__ import annotations

import os
from langgraph.graph import StateGraph, END

from .state import AgentState
from .nodes import (
    plan_node,
    tool_node,
    grade_evidence_node,
    synthesize_node
)


def _route_after_grade(state: AgentState) -> str:
    """Conditional edge after grading evidence."""
    # Default to 1 to match TUI and config expectations
    max_iter = max(1, min(5, int(os.getenv("KB_AGENT_MAX_ITERATIONS", "1"))))
    
    action = state.get("grader_action", "GENERATE")
    
    if action == "GENERATE":
        return "synthesize"
        
    if state.get("iteration", 0) >= max_iter:
        return "synthesize"
        
    if action == "REFINE":
        return "plan"
        
    if action == "RE_RETRIEVE":
        return "plan"
        
    return "synthesize" # Fallback


def _route_after_tool_exec(state: AgentState) -> str:
    """Conditional edge after tool_exec: skip grading for simple queries."""
    return "grade_evidence"


def build_graph() -> StateGraph:
    """Construct (but do not compile) the agentic RAG graph."""
    graph = StateGraph(AgentState)

    # Add nodes
    graph.add_node("plan", plan_node)
    graph.add_node("tool_exec", tool_node)
    graph.add_node("grade_evidence", grade_evidence_node)
    graph.add_node("synthesize", synthesize_node)

    # Edges
    graph.set_entry_point("plan")
    graph.add_edge("plan", "tool_exec")
    graph.add_conditional_edges("tool_exec", _route_after_tool_exec)
    graph.add_conditional_edges("grade_evidence", _route_after_grade)
    graph.add_edge("synthesize", END)

    return graph


def compile_graph():
    """Build and compile the graph, ready to ``.invoke()``."""
    return build_graph().compile()
