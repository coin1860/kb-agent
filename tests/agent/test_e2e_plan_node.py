import pytest
from unittest.mock import patch, MagicMock
from langchain_core.messages import AIMessage
from kb_agent.agent.nodes import plan_node

def _noop_status(emoji, msg):
    pass

@patch("kb_agent.agent.nodes._build_llm")
def test_plan_node_e2e_conceptual_chinese(mock_build):
    # 4.1 端到端测试：概念型中文问题（如 "Introduction里面没写什么？"）
    # 应只调用 vector_search，不调用 jira_fetch/confluence_fetch/web_fetch
    mock_llm = MagicMock()
    # Simulate a completely botched LLM output that mentions everything
    mock_llm.invoke.return_value = AIMessage(
        content="我看看，可以用 jira_fetch，再去 confluence_fetch，或者 web_fetch，最后用 vector_search。"
    )
    mock_build.return_value = mock_llm

    state = {
        "query": "Introduction里面没写什么？",
        "messages": [],
        "context": [],
        "iteration": 0,
        "routing_plan": {
            "query_type": "conceptual",
            "suggested_tools": ["vector_search"],
            "sub_questions": []
        },
        "status_callback": _noop_status,
    }

    result = plan_node(state)
    tool_calls = result.get("pending_tool_calls", [])
    names = [t["name"] for t in tool_calls]
    
    assert "vector_search" in names
    assert "jira_fetch" not in names
    assert "confluence_fetch" not in names
    assert "web_fetch" not in names

@patch("kb_agent.agent.nodes._build_llm")
def test_plan_node_e2e_jira_ticket(mock_build):
    # 4.2 端到端测试：包含 Jira ticket 的问题（如 "PROJ-123 的状态"）应调用 jira_fetch(issue_key="PROJ-123")
    mock_llm = MagicMock()
    # LLM fallback
    mock_llm.invoke.return_value = AIMessage(
        content="帮我用 jira_fetch 查一下 PROJ-123 的状态"
    )
    mock_build.return_value = mock_llm

    state = {
        "query": "PROJ-123 的状态是什么？",
        "messages": [],
        "context": [],
        "iteration": 0,
        "routing_plan": {
            "query_type": "exact",
            "suggested_tools": ["jira_fetch", "grep_search"],
            "sub_questions": []
        },
        "status_callback": _noop_status,
    }

    result = plan_node(state)
    tool_calls = result.get("pending_tool_calls", [])
    
    # Needs to match exactly issue_key: PROJ-123
    jira_call = next((t for t in tool_calls if t["name"] == "jira_fetch"), None)
    assert jira_call is not None
    assert jira_call["args"]["issue_key"] == "PROJ-123"

@patch("kb_agent.agent.nodes._build_llm")
def test_plan_node_e2e_url(mock_build):
    # 4.3 端到端测试：包含 URL 的问题应调用 web_fetch(url="https://...")
    mock_llm = MagicMock()
    mock_llm.invoke.return_value = AIMessage(content="请用 web_fetch 获取内容")
    mock_build.return_value = mock_llm

    url = "https://example.com/spec"
    state = {
        "query": f"总结 {url} 的内容",
        "messages": [],
        "context": [],
        "iteration": 0,
        "routing_plan": {
            "query_type": "conceptual",
            "suggested_tools": ["web_fetch"],
            "sub_questions": []
        },
        "status_callback": _noop_status,
    }

    result = plan_node(state)
    tool_calls = result.get("pending_tool_calls", [])
    
    web_call = next((t for t in tool_calls if t["name"] == "web_fetch"), None)
    assert web_call is not None
    assert web_call["args"]["url"] == url

def test_plan_node_e2e_complex_sub_questions():
    # 4.4 端到端测试：复杂多部分问题应拆分为子问题，每个子问题独立检索
    # The sub-question fast path explicitly skips the LLM call entirely.
    state = {
        "query": "Compare indexing and query engines",
        "messages": [],
        "context": [],
        "iteration": 0,
        "routing_plan": {
            "query_type": "conceptual",
            "suggested_tools": ["hybrid_search"],
            "sub_questions": ["indexing architecture", "query engine concepts"]
        },
        "status_callback": _noop_status,
    }

    result = plan_node(state)
    tool_calls = result.get("pending_tool_calls", [])
    
    # Expected output: 2 tool calls because 2 sub-questions
    assert len(tool_calls) == 2
    assert tool_calls[0]["name"] == "hybrid_search"
    assert tool_calls[0]["args"]["semantic_query"] == "indexing architecture"
    
    assert tool_calls[1]["name"] == "hybrid_search"
    assert tool_calls[1]["args"]["semantic_query"] == "query engine concepts"
