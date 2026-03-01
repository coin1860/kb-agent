import pytest
from kb_agent.agent.nodes import _is_tool_applicable, _build_tool_args, _extract_tools_from_text

def test_is_tool_applicable():
    assert _is_tool_applicable("jira_fetch", "What is PROJ-123?") == True
    assert _is_tool_applicable("jira_fetch", "What is Introduction?") == False
    
    assert _is_tool_applicable("confluence_fetch", "Check page 123456") == True
    assert _is_tool_applicable("confluence_fetch", "Check confluence for this") == True
    assert _is_tool_applicable("confluence_fetch", "What is Introduction?") == False
    
    assert _is_tool_applicable("web_fetch", "Read http://example.com") == True
    assert _is_tool_applicable("web_fetch", "Read https://example.com") == True
    assert _is_tool_applicable("web_fetch", "Read example.com") == False

    assert _is_tool_applicable("vector_search", "Anything") == True

def test_build_tool_args():
    assert _build_tool_args("vector_search", "Test") == {"query": "Test"}
    assert _build_tool_args("grep_search", "Test") == {"query": "Test"}
    assert _build_tool_args("read_file", "path.md") == {"file_path": "path.md"}
    
    assert _build_tool_args("jira_fetch", "What is PROJ-123?") == {"issue_key": "PROJ-123"}
    assert _build_tool_args("jira_fetch", "No ticket") == None
    
    assert _build_tool_args("confluence_fetch", "Read page 123456") == {"page_id": "123456"}
    assert _build_tool_args("web_fetch", "Here is https://example.com/spec") == {"url": "https://example.com/spec"}
    assert _build_tool_args("web_fetch", "No URL") == None
    
    # Test dictionary queries for semantic & keyword separation
    dict_query = {"semantic_intent": "compare indexing logic", "search_keywords": "index query"}
    
    assert _build_tool_args("hybrid_search", dict_query) == {
        "semantic_query": "compare indexing logic", 
        "exact_keywords": "index query"
    }
    
    assert _build_tool_args("vector_search", dict_query) == {
        "query": "compare indexing logic"
    }
    
    assert _build_tool_args("grep_search", dict_query) == {
        "query": "index query"
    }
    
    # Test fallback if keywords empty
    dict_query_empty_kx = {"semantic_intent": "missing words", "search_keywords": ""}
    assert _build_tool_args("grep_search", dict_query_empty_kx) == {
        "query": "missing words"
    }

def test_extract_tools_from_text():
    # Test fallback extraction with no white list
    text = "Let's use vector_search and jira_fetch for PROJ-123"
    tools = _extract_tools_from_text(text, "query about PROJ-123")
    names = [t["name"] for t in tools]
    assert "vector_search" in names
    assert "jira_fetch" in names
    
    # Test allowed_tools whitelist
    tools2 = _extract_tools_from_text(text, "query about PROJ-123", allowed_tools=["vector_search"])
    names2 = [t["name"] for t in tools2]
    assert "vector_search" in names2
    assert "jira_fetch" not in names2

    # Test applicability guard — mention jira but no pattern in query
    text3 = "I could use jira_fetch"
    tools3 = _extract_tools_from_text(text3, "Introduction没写什么?")
    names3 = [t["name"] for t in tools3]
    assert "jira_fetch" not in names3
