"""
LangGraph workflow definition for the agentic RAG pipeline.

Topology:
    START → plan → tool_exec → evaluate
                                  ├─ sufficient ──────────→ synthesize → END
                                  └─ not sufficient & i<3 → plan (loop)
                                  └─ not sufficient & i≥3 → synthesize → END
"""

from __future__ import annotations

from langgraph.graph import StateGraph, END

from .state import AgentState
from .nodes import plan_node, tool_node, evaluate_node, synthesize_node


def _route_after_evaluate(state: AgentState) -> str:
    """Conditional edge after the evaluate node."""
    import os
    max_iter = max(1, min(5, int(os.getenv("KB_AGENT_MAX_ITERATIONS", "1"))))
    if state.get("is_sufficient"):
        return "synthesize"
    if state.get("iteration", 0) >= max_iter:
        return "synthesize"
    return "plan"


def build_graph() -> StateGraph:
    """Construct (but do not compile) the agentic RAG graph."""
    graph = StateGraph(AgentState)

    # Add nodes
    graph.add_node("plan", plan_node)
    graph.add_node("tool_exec", tool_node)
    graph.add_node("evaluate", evaluate_node)
    graph.add_node("synthesize", synthesize_node)

    # Edges
    graph.set_entry_point("plan")
    graph.add_edge("plan", "tool_exec")
    graph.add_edge("tool_exec", "evaluate")
    graph.add_conditional_edges("evaluate", _route_after_evaluate)
    graph.add_edge("synthesize", END)

    return graph


def compile_graph():
    """Build and compile the graph, ready to ``.invoke()``."""
    return build_graph().compile()
