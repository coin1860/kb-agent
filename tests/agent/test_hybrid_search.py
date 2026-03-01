import pytest
import json
from unittest.mock import MagicMock
from kb_agent.agent.tools import hybrid_search, _get_grep, _get_vector

@pytest.fixture(autouse=True)
def mock_tools(mocker):
    # Mock the lazy singletons
    mock_grep = MagicMock()
    mock_vector = MagicMock()
    mocker.patch("kb_agent.agent.tools._get_grep", return_value=mock_grep)
    mocker.patch("kb_agent.agent.tools._get_vector", return_value=mock_vector)
    return mock_grep, mock_vector

def test_hybrid_search_fusion(mock_tools):
    mock_grep, mock_vector = mock_tools
    
    # Grep returns file A and file B
    mock_grep.search.return_value = [
        {"file_path": "file_A.md", "line": 10, "content": "Grep match A"},
        {"file_path": "file_B.md", "line": 20, "content": "Grep match B"}
    ]
    
    # Vector returns file B and file C
    mock_vector.search.return_value = [
        {"id": "doc_b1", "content": "Vector match B", "metadata": {"source": "file_B.md"}},
        {"id": "doc_c1", "content": "Vector match C", "metadata": {"source": "file_C.md"}}
    ]
    
    # Call hybrid search
    result_str = hybrid_search.invoke({"semantic_query": "test query", "exact_keywords": "grep test"})
    results = json.loads(result_str)
    
    assert len(results) == 3
    paths = [r["file_path"] for r in results]
    
    # file_B.md should be ranked first because it appears in both (Rank 2 in grep, Rank 1 in vector)
    # RRF(B) = 1/(60+2) + 1/(60+1) ≈ 0.0161 + 0.0163 ≈ 0.0324
    # RRF(A) = 1/(60+1) ≈ 0.0163
    # RRF(C) = 1/(60+2) ≈ 0.0161
    # Thus order should be B, A, C
    assert paths == ["file_B.md", "file_A.md", "file_C.md"]

def test_hybrid_search_grep_only(mock_tools):
    mock_grep, mock_vector = mock_tools
    
    mock_grep.search.return_value = [
        {"file_path": "file_A.md", "line": 10, "content": "Grep match A"}
    ]
    mock_vector.search.return_value = []
    
    result_str = hybrid_search.invoke({"semantic_query": "test query"})
    results = json.loads(result_str)
    
    assert len(results) == 1
    assert results[0]["file_path"] == "file_A.md"

def test_hybrid_search_vector_only(mock_tools):
    mock_grep, mock_vector = mock_tools
    
    mock_grep.search.return_value = []
    mock_vector.search.return_value = [
        {"id": "doc_b1", "content": "Vector match B", "metadata": {"source": "file_B.md"}}
    ]
    
    result_str = hybrid_search.invoke({"semantic_query": "test query", "exact_keywords": "keyword"})
    results = json.loads(result_str)
    
    assert len(results) == 1
    assert results[0]["file_path"] == "file_B.md"

def test_hybrid_search_both_empty(mock_tools):
    mock_grep, mock_vector = mock_tools
    
    mock_grep.search.return_value = []
    mock_vector.search.return_value = []
    
    result_str = hybrid_search.invoke({"semantic_query": "test query"})
    results = json.loads(result_str)
    
    assert len(results) == 0
