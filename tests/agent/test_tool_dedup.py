import pytest
import json
from unittest.mock import patch, MagicMock
from kb_agent.agent.nodes import tool_node

def _noop_status(emoji, msg):
    pass

@patch("kb_agent.agent.nodes.ALL_TOOLS")
def test_tool_node_chunk_dedup(mock_all_tools):
    # Mock vector_search to return slightly different chunks based on query
    def mock_invoke(args):
        if "query_1" in args.get("query", ""):
            return json.dumps([
                {"id": "doc1:L10", "content": "Chunk A", "metadata": {"path": "doc1", "line": 10}, "score": 0.8},
                {"id": "doc2:L20", "content": "Chunk B", "metadata": {"path": "doc2", "line": 20}, "score": 0.5},
            ])
        else:
            return json.dumps([
                {"id": "doc1:L10", "content": "Chunk A (same id)", "metadata": {"path": "doc1", "line": 10}, "score": 0.95},
                {"id": "doc3:L30", "content": "Chunk C", "metadata": {"path": "doc3", "line": 30}, "score": 0.7},
            ])

    mock_tool = MagicMock()
    mock_tool.name = "vector_search"
    mock_tool.invoke = mock_invoke
    
    # We also need a dummy read_file to not fail the ALL_TOOLS dict comprehension, but tool_name doesn't matter
    # if we only pass vector_search
    mock_all_tools.__iter__.return_value = [mock_tool]

    state = {
        "pending_tool_calls": [
            {"name": "vector_search", "args": {"query": "query_1"}},
            {"name": "vector_search", "args": {"query": "query_2"}},
        ],
        "context": [],
        "tool_history": [],
        "files_read": [],
        "status_callback": _noop_status,
    }

    result = tool_node(state)
    context = result.get("context", [])
    
    # We should have exactly 3 chunks: doc1:L10, doc2:L20, doc3:L30
    assert len(context) == 3
    
    # doc1:L10 should have the higher score (0.95)
    doc1_content = [c for c in context if "doc1:L10" in c][0]
    assert "S0.95" in doc1_content
    assert "Chunk A (same id)" in doc1_content
    
    # Other chunks should be present
    assert any("doc2:L20" in c for c in context)
    assert any("doc3:L30" in c for c in context)
