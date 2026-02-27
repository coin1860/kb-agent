"""
Tests for Engine — the public API (post-LangGraph refactor).

Validates that:
- Knowledge Base mode delegates to the compiled LangGraph.
- Normal mode uses direct LLM chat.
- URL mode works unchanged.
"""

import os
import json
from unittest.mock import patch, MagicMock

# Dummy env vars for config
os.environ.setdefault("KB_AGENT_LLM_API_KEY", "dummy")
os.environ.setdefault("KB_AGENT_LLM_BASE_URL", "http://dummy")


class TestEngineNormalMode:
    """Normal (non-RAG) mode should bypass the graph and call LLMClient directly."""

    @patch("kb_agent.engine.compile_graph")
    @patch("kb_agent.engine.LLMClient")
    def test_normal_mode_direct_llm(self, MockLLM, MockGraph):
        mock_llm = MockLLM.return_value
        mock_llm.chat_completion.return_value = "Hello from normal mode!"

        from kb_agent.engine import Engine
        engine = Engine()

        answer = engine.answer_query("hi", mode="normal")

        assert "Hello from normal mode!" in answer
        mock_llm.chat_completion.assert_called_once()
        # Graph should NOT be invoked
        MockGraph.return_value.invoke.assert_not_called()

    @patch("kb_agent.engine.compile_graph")
    @patch("kb_agent.engine.LLMClient")
    def test_normal_mode_includes_history(self, MockLLM, MockGraph):
        mock_llm = MockLLM.return_value
        mock_llm.chat_completion.return_value = "Sure, continuing..."

        from kb_agent.engine import Engine
        engine = Engine()

        history = [
            {"role": "user", "content": "Hi"},
            {"role": "assistant", "content": "Hello!"},
        ]

        answer = engine.answer_query("Tell me more", mode="normal", history=history)

        args, kwargs = mock_llm.chat_completion.call_args
        messages = args[0]
        # system + 2 history + user message
        assert len(messages) == 4
        assert messages[0]["role"] == "system"
        assert messages[-1]["content"] == "Tell me more"


class TestEngineKBMode:
    """Knowledge Base mode should delegate to the LangGraph compiled graph."""

    @patch("kb_agent.engine.compile_graph")
    @patch("kb_agent.engine.LLMClient")
    def test_kb_mode_invokes_graph(self, MockLLM, MockGraph):
        mock_graph = MockGraph.return_value
        mock_graph.invoke.return_value = {
            "final_answer": "The project is on track based on DOC-1."
        }

        from kb_agent.engine import Engine
        engine = Engine()

        answer = engine.answer_query("What is the status of Project X?")

        assert "on track" in answer
        mock_graph.invoke.assert_called_once()

        # Verify initial state structure
        call_args = mock_graph.invoke.call_args[0][0]
        assert call_args["query"] == "What is the status of Project X?"
        assert call_args["mode"] == "knowledge_base"
        assert call_args["iteration"] == 0
        assert call_args["context"] == []

    @patch("kb_agent.engine.compile_graph")
    @patch("kb_agent.engine.LLMClient")
    def test_kb_mode_passes_history(self, MockLLM, MockGraph):
        mock_graph = MockGraph.return_value
        mock_graph.invoke.return_value = {"final_answer": "Follow-up answer"}

        from kb_agent.engine import Engine
        engine = Engine()

        history = [
            {"role": "user", "content": "What is Project X?"},
            {"role": "assistant", "content": "Project X is..."},
        ]

        answer = engine.answer_query("Tell me more", history=history)

        call_args = mock_graph.invoke.call_args[0][0]
        assert call_args["messages"] == history

    @patch("kb_agent.engine.compile_graph")
    @patch("kb_agent.engine.LLMClient")
    def test_kb_mode_empty_answer_fallback(self, MockLLM, MockGraph):
        mock_graph = MockGraph.return_value
        mock_graph.invoke.return_value = {"final_answer": ""}

        from kb_agent.engine import Engine
        engine = Engine()

        answer = engine.answer_query("Unknown topic")

        assert "couldn't find" in answer.lower()

    @patch("kb_agent.engine.compile_graph")
    @patch("kb_agent.engine.LLMClient")
    def test_kb_mode_graph_error_handled(self, MockLLM, MockGraph):
        mock_graph = MockGraph.return_value
        mock_graph.invoke.side_effect = RuntimeError("LLM connection failed")

        from kb_agent.engine import Engine
        engine = Engine()

        answer = engine.answer_query("test query")

        assert "error" in answer.lower()

    @patch("kb_agent.engine.compile_graph")
    @patch("kb_agent.engine.LLMClient")
    def test_kb_mode_status_callback_passed(self, MockLLM, MockGraph):
        mock_graph = MockGraph.return_value
        mock_graph.invoke.return_value = {"final_answer": "test"}

        from kb_agent.engine import Engine
        engine = Engine()

        status_calls = []
        answer = engine.answer_query(
            "test",
            on_status=lambda e, m: status_calls.append((e, m)),
        )

        # At minimum, the engine emits "Starting agentic RAG workflow..."
        assert len(status_calls) >= 1
        assert any("🚀" in e for e, m in status_calls)

        # The callback is also passed into the graph state
        call_args = mock_graph.invoke.call_args[0][0]
        assert call_args["status_callback"] is not None


class TestEngineURLMode:
    """URL handling should still work unchanged."""

    @patch("kb_agent.engine.compile_graph")
    @patch("kb_agent.engine.WebConnector")
    @patch("kb_agent.engine.LLMClient")
    def test_url_detection(self, MockLLM, MockWeb, MockGraph):
        mock_llm = MockLLM.return_value
        mock_web = MockWeb.return_value
        
        mock_web.fetch_data.return_value = [{
            "id": "web_test",
            "title": "Test Page",
            "content": "Page content here",
            "metadata": {"source": "web", "url": "https://example.com"},
        }]
        mock_llm.chat_completion.return_value = "Summary of the page"

        from kb_agent.engine import Engine
        engine = Engine()

        answer = engine.answer_query("https://example.com what is this?")

        assert "Summary" in answer
        mock_web.fetch_data.assert_called_once()
        # Graph should NOT be invoked for URL queries
        MockGraph.return_value.invoke.assert_not_called()
