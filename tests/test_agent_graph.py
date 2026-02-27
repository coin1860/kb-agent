"""
Tests for the agentic RAG LangGraph workflow.

All LLM calls are mocked so tests run without an API key.
"""

import os
import json
from unittest.mock import patch, MagicMock, ANY

# Ensure dummy env vars before any imports that touch config
os.environ.setdefault("KB_AGENT_LLM_API_KEY", "test-key")
os.environ.setdefault("KB_AGENT_LLM_BASE_URL", "http://test")

import pytest
from langchain_core.messages import AIMessage


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_ai_message(content: str) -> AIMessage:
    """Plain text response (no tool calls)."""
    return AIMessage(content=content)


def _noop_status(emoji, msg):
    """Stub status callback."""
    pass


# ---------------------------------------------------------------------------
# 1. Plan node produces tool calls from JSON response
# ---------------------------------------------------------------------------

class TestPlanNode:
    @patch("kb_agent.agent.nodes._build_llm")
    def test_plan_parses_json_tool_calls(self, mock_build):
        mock_llm = MagicMock()
        # Planner returns JSON array of tool calls
        mock_llm.invoke.return_value = _make_ai_message(
            '[{"name": "grep_search", "args": {"query": "login flow"}}]'
        )
        mock_build.return_value = mock_llm

        from kb_agent.agent.nodes import plan_node

        state = {
            "query": "How does the login flow work?",
            "messages": [],
            "context": [],
            "iteration": 0,
            "status_callback": _noop_status,
        }

        result = plan_node(state)
        assert "pending_tool_calls" in result
        assert len(result["pending_tool_calls"]) == 1
        assert result["pending_tool_calls"][0]["name"] == "grep_search"

    @patch("kb_agent.agent.nodes._build_llm")
    def test_plan_fallback_on_invalid_json(self, mock_build):
        mock_llm = MagicMock()
        mock_llm.invoke.return_value = _make_ai_message(
            "I should search for login flow..."  # Not valid JSON
        )
        mock_build.return_value = mock_llm

        from kb_agent.agent.nodes import plan_node

        state = {
            "query": "login flow",
            "messages": [],
            "context": [],
            "iteration": 0,
            "status_callback": _noop_status,
        }

        result = plan_node(state)
        # Should fallback to grep + vector search
        assert len(result["pending_tool_calls"]) == 2
        names = [t["name"] for t in result["pending_tool_calls"]]
        assert "grep_search" in names
        assert "vector_search" in names

    @patch("kb_agent.agent.nodes._build_llm")
    def test_plan_handles_native_tool_calls(self, mock_build):
        """If the LLM supports native tool_calls, use them."""
        mock_llm = MagicMock()
        resp = AIMessage(content="", tool_calls=[
            {"name": "grep_search", "args": {"query": "test"}, "id": "c1"}
        ])
        mock_llm.invoke.return_value = resp
        mock_build.return_value = mock_llm

        from kb_agent.agent.nodes import plan_node

        state = {
            "query": "test query",
            "messages": [],
            "context": [],
            "iteration": 0,
            "status_callback": _noop_status,
        }

        result = plan_node(state)
        assert len(result["pending_tool_calls"]) == 1
        assert result["pending_tool_calls"][0]["name"] == "grep_search"


# ---------------------------------------------------------------------------
# 2. Tool node executes calls
# ---------------------------------------------------------------------------

class TestToolNode:
    @patch("kb_agent.agent.tools._get_grep")
    def test_tool_node_executes_grep(self, mock_get_grep):
        mock_grep_instance = MagicMock()
        mock_grep_instance.search.return_value = [
            {"file_path": "DOC-1.md", "content": "login info", "line": 5}
        ]
        mock_get_grep.return_value = mock_grep_instance

        from kb_agent.agent.nodes import tool_node

        state = {
            "query": "login",
            "pending_tool_calls": [
                {"name": "grep_search", "args": {"query": "login"}}
            ],
            "context": [],
            "tool_history": [],
            "files_read": [],
            "status_callback": _noop_status,
        }

        result = tool_node(state)
        assert len(result["context"]) == 1
        assert "grep_search" in result["context"][0]
        assert len(result["tool_history"]) == 1

    def test_tool_node_no_pending(self):
        from kb_agent.agent.nodes import tool_node

        state = {
            "query": "test",
            "pending_tool_calls": [],
            "context": ["existing"],
            "tool_history": [],
            "files_read": [],
            "status_callback": _noop_status,
        }

        result = tool_node(state)
        assert result["context"] == ["existing"]


# ---------------------------------------------------------------------------
# 3. Evaluate node — sufficient / not sufficient
# ---------------------------------------------------------------------------

class TestEvaluateNode:
    @patch("kb_agent.agent.nodes._build_llm")
    def test_evaluate_sufficient(self, mock_build):
        mock_llm = MagicMock()
        mock_llm.invoke.return_value = _make_ai_message('{"sufficient": true}')
        mock_build.return_value = mock_llm

        from kb_agent.agent.nodes import evaluate_node

        state = {
            "query": "What is X?",
            "messages": [],
            "context": ["[grep_search] found X info"],
            "iteration": 0,
            "status_callback": _noop_status,
        }

        result = evaluate_node(state)
        assert result["is_sufficient"] is True
        assert result["iteration"] == 1

    @patch("kb_agent.agent.nodes._build_llm")
    def test_evaluate_not_sufficient(self, mock_build):
        mock_llm = MagicMock()
        mock_llm.invoke.return_value = _make_ai_message(
            '{"sufficient": false, "reason": "missing details"}'
        )
        mock_build.return_value = mock_llm

        from kb_agent.agent.nodes import evaluate_node

        state = {
            "query": "What is X?",
            "messages": [],
            "context": ["[grep_search] partial info"],
            "iteration": 0,
            "status_callback": _noop_status,
        }

        result = evaluate_node(state)
        assert result["is_sufficient"] is False

    def test_evaluate_no_context(self):
        from kb_agent.agent.nodes import evaluate_node

        state = {
            "query": "What is X?",
            "messages": [],
            "context": [],
            "iteration": 0,
            "status_callback": _noop_status,
        }

        result = evaluate_node(state)
        assert result["is_sufficient"] is False


# ---------------------------------------------------------------------------
# 4. Synthesize node — grounded answer
# ---------------------------------------------------------------------------

class TestSynthesizeNode:
    @patch("kb_agent.agent.nodes._build_llm")
    def test_synthesize_with_context(self, mock_build):
        mock_llm = MagicMock()
        mock_llm.invoke.return_value = _make_ai_message("The login flow works by...")
        mock_build.return_value = mock_llm

        from kb_agent.agent.nodes import synthesize_node

        state = {
            "query": "How does login work?",
            "messages": [],
            "context": ["[grep_search] login flow details..."],
            "status_callback": _noop_status,
        }

        result = synthesize_node(state)
        assert "login flow" in result["final_answer"].lower()

    @patch("kb_agent.agent.nodes._build_llm")
    def test_synthesize_no_context_refuses(self, mock_build):
        mock_llm = MagicMock()
        mock_llm.invoke.return_value = _make_ai_message(
            "I couldn't find relevant information in the knowledge base."
        )
        mock_build.return_value = mock_llm

        from kb_agent.agent.nodes import synthesize_node

        state = {
            "query": "What is quantum computing?",
            "messages": [],
            "context": [],
            "status_callback": _noop_status,
        }

        result = synthesize_node(state)
        assert "couldn't find" in result["final_answer"].lower()


# ---------------------------------------------------------------------------
# 5. Conditional routing
# ---------------------------------------------------------------------------

class TestRouting:
    @patch.dict(os.environ, {"KB_AGENT_MAX_ITERATIONS": "3"})
    def test_route_sufficient(self):
        from kb_agent.agent.graph import _route_after_evaluate
        assert _route_after_evaluate({"is_sufficient": True, "iteration": 1}) == "synthesize"

    @patch.dict(os.environ, {"KB_AGENT_MAX_ITERATIONS": "3"})
    def test_route_not_sufficient_under_limit(self):
        from kb_agent.agent.graph import _route_after_evaluate
        assert _route_after_evaluate({"is_sufficient": False, "iteration": 1}) == "plan"

    @patch.dict(os.environ, {"KB_AGENT_MAX_ITERATIONS": "3"})
    def test_route_max_iterations(self):
        from kb_agent.agent.graph import _route_after_evaluate
        assert _route_after_evaluate({"is_sufficient": False, "iteration": 3}) == "synthesize"

    @patch.dict(os.environ, {"KB_AGENT_MAX_ITERATIONS": "3"})
    def test_route_exactly_at_limit(self):
        from kb_agent.agent.graph import _route_after_evaluate
        assert _route_after_evaluate({"is_sufficient": False, "iteration": 4}) == "synthesize"


# ---------------------------------------------------------------------------
# 6. Status callback invocation
# ---------------------------------------------------------------------------

class TestStatusCallback:
    @patch("kb_agent.agent.nodes._build_llm")
    def test_plan_emits_status(self, mock_build):
        mock_llm = MagicMock()
        mock_llm.invoke.return_value = _make_ai_message('[]')
        mock_build.return_value = mock_llm

        from kb_agent.agent.nodes import plan_node

        status_calls = []
        state = {
            "query": "test",
            "messages": [],
            "context": [],
            "iteration": 0,
            "status_callback": lambda e, m: status_calls.append((e, m)),
        }

        plan_node(state)
        assert len(status_calls) >= 1
        assert any("🧠" in e for e, m in status_calls)

    @patch("kb_agent.agent.nodes._build_llm")
    def test_evaluate_emits_status(self, mock_build):
        mock_llm = MagicMock()
        mock_llm.invoke.return_value = _make_ai_message('{"sufficient": true}')
        mock_build.return_value = mock_llm

        from kb_agent.agent.nodes import evaluate_node

        status_calls = []
        state = {
            "query": "test",
            "messages": [],
            "context": ["some context"],
            "iteration": 0,
            "status_callback": lambda e, m: status_calls.append((e, m)),
        }

        evaluate_node(state)
        assert len(status_calls) >= 1
        assert any("🤔" in e for e, m in status_calls)


# ---------------------------------------------------------------------------
# 7. Multi-turn history
# ---------------------------------------------------------------------------

class TestMultiTurn:
    @patch("kb_agent.agent.nodes._build_llm")
    def test_plan_receives_history(self, mock_build):
        mock_llm = MagicMock()
        mock_llm.invoke.return_value = _make_ai_message('[]')
        mock_build.return_value = mock_llm

        from kb_agent.agent.nodes import plan_node

        history = [
            {"role": "user", "content": "What is project X?"},
            {"role": "assistant", "content": "Project X is about..."},
        ]

        state = {
            "query": "Tell me more about its timeline",
            "messages": history,
            "context": [],
            "iteration": 0,
            "status_callback": _noop_status,
        }

        plan_node(state)
        call_args = mock_llm.invoke.call_args[0][0]
        # SystemMessage + 2 history + HumanMessage = 4+
        assert len(call_args) >= 4

    @patch("kb_agent.agent.nodes._build_llm")
    def test_synthesize_receives_history(self, mock_build):
        mock_llm = MagicMock()
        mock_llm.invoke.return_value = _make_ai_message("Based on the history...")
        mock_build.return_value = mock_llm

        from kb_agent.agent.nodes import synthesize_node

        state = {
            "query": "Tell me more",
            "messages": [
                {"role": "user", "content": "What is project X?"},
                {"role": "assistant", "content": "Project X is about..."},
            ],
            "context": ["[grep_search] timeline data"],
            "status_callback": _noop_status,
        }

        synthesize_node(state)
        call_args = mock_llm.invoke.call_args[0][0]
        assert len(call_args) >= 4


# ---------------------------------------------------------------------------
# 8. Anti-hallucination: synthesizer prompt
# ---------------------------------------------------------------------------

class TestAntiHallucination:
    @patch("kb_agent.agent.nodes._build_llm")
    def test_synthesize_prompt_contains_grounding_instruction(self, mock_build):
        mock_llm = MagicMock()
        mock_llm.invoke.return_value = _make_ai_message("test answer")
        mock_build.return_value = mock_llm

        from kb_agent.agent.nodes import synthesize_node

        state = {
            "query": "test",
            "messages": [],
            "context": ["some context"],
            "status_callback": _noop_status,
        }

        synthesize_node(state)
        call_args = mock_llm.invoke.call_args[0][0]
        system_msg = call_args[0].content
        assert "ONLY" in system_msg
        assert "Do NOT use your own knowledge" in system_msg
