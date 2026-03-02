import pytest
from unittest.mock import patch, MagicMock
from langchain_core.messages import AIMessage
from kb_agent.agent.nodes import _decompose_query

def _noop_status(emoji, msg):
    pass

@patch("kb_agent.agent.nodes._build_llm")
def test_decompose_query_vector(mock_build):
    mock_llm = MagicMock()
    mock_llm.invoke.return_value = AIMessage(
        content='{"action": "decompose", "sub_queries": ["Intro什么没写", "Introduction missing", "Intro omitted"]}'
    )
    mock_build.return_value = mock_llm
    
    state = {
        "status_callback": _noop_status,
        "llm_call_count": 0,
        "llm_prompt_tokens": 0,
        "llm_total_tokens": 0,
        "llm_completion_tokens": 0
    }
    
    result = _decompose_query("Introduction里面没写什么？", state)
    
    assert len(result) == 3
    assert all(t["name"] == "vector_search" for t in result)
    assert result[0]["args"]["query"] == "Intro什么没写"
    assert result[1]["args"]["query"] == "Introduction missing"
    assert result[2]["args"]["query"] == "Intro omitted"

@patch("kb_agent.agent.nodes._build_llm")
def test_decompose_query_jira(mock_build):
    mock_llm = MagicMock()
    mock_llm.invoke.return_value = AIMessage(
        content='{"action": "direct", "tool": "jira_fetch", "args": {"issue_key": "PROJ-123"}}'
    )
    mock_build.return_value = mock_llm
    
    state = {
        "status_callback": _noop_status,
        "llm_call_count": 0,
        "llm_prompt_tokens": 0,
        "llm_total_tokens": 0,
        "llm_completion_tokens": 0
    }
    
    result = _decompose_query("PROJ-123 的状态是什么？", state)
    
    assert len(result) == 1
    assert result[0]["name"] == "jira_fetch"
    assert result[0]["args"]["issue_key"] == "PROJ-123"

@patch("kb_agent.agent.nodes._build_llm")
def test_decompose_query_fallback(mock_build):
    mock_llm = MagicMock()
    mock_llm.invoke.return_value = AIMessage(
        content="This is bad output from the LLM"
    )
    mock_build.return_value = mock_llm
    
    state = {
        "status_callback": _noop_status,
        "llm_call_count": 0,
        "llm_prompt_tokens": 0,
        "llm_total_tokens": 0,
        "llm_completion_tokens": 0
    }
    
    query = "Fallback question"
    result = _decompose_query(query, state)
    
    assert len(result) == 1
    assert result[0]["name"] == "vector_search"
    assert result[0]["args"]["query"] == query
