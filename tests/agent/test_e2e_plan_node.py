import pytest
from unittest.mock import patch, MagicMock
from langchain_core.messages import AIMessage
from kb_agent.agent.nodes import plan_node

def _noop_status(emoji, msg):
    pass

@patch("kb_agent.agent.nodes._build_llm")
def test_plan_node_e2e_conceptual_chinese(mock_build):
    # 4.1. Round 1 should trigger _decompose_query and return 3 vector_search calls
    mock_llm = MagicMock()
    # Mock decompose JSON output
    mock_llm.invoke.return_value = AIMessage(
        content='{"action": "decompose", "sub_queries": ["Intro什么没写", "Introduction missing", "Intro omitted"]}'
    )
    mock_build.return_value = mock_llm

    state = {
        "query": "Introduction里面没写什么？",
        "messages": [],
        "context": [],
        "iteration": 0,
        "status_callback": _noop_status,
        "llm_call_count": 0,
        "llm_prompt_tokens": 0,
        "llm_total_tokens": 0,
        "llm_completion_tokens": 0
    }

    result = plan_node(state)
    tool_calls = result.get("pending_tool_calls", [])
    
    assert len(tool_calls) == 3
    assert all(t["name"] == "vector_search" for t in tool_calls)
    assert tool_calls[0]["args"]["query"] == "Intro什么没写"

@patch("kb_agent.agent.nodes._build_llm")
def test_plan_node_e2e_jira_ticket(mock_build):
    # 4.2. Round 1 should trigger _decompose_query which detects Jira directly
    mock_llm = MagicMock()
    mock_llm.invoke.return_value = AIMessage(
        content='{"action": "direct", "tool": "jira_fetch", "args": {"issue_key": "PROJ-123"}}'
    )
    mock_build.return_value = mock_llm

    state = {
        "query": "PROJ-123 的状态是什么？",
        "messages": [],
        "context": [],
        "iteration": 0,
        "status_callback": _noop_status,
        "llm_call_count": 0,
        "llm_prompt_tokens": 0,
        "llm_total_tokens": 0,
        "llm_completion_tokens": 0
    }

    result = plan_node(state)
    tool_calls = result.get("pending_tool_calls", [])
    
    assert len(tool_calls) == 1
    assert tool_calls[0]["name"] == "jira_fetch"
    assert tool_calls[0]["args"]["issue_key"] == "PROJ-123"


