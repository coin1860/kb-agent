import pytest
from unittest.mock import MagicMock, patch
from kb_agent.tools.vector_tool import VectorTool

@pytest.fixture
def mock_config():
    with patch('kb_agent.tools.vector_tool.config.settings', new_callable=MagicMock) as mock_settings:
        mock_settings.vector_score_threshold = 0.5
        mock_settings.use_reranker = False
        mock_settings.docs_path = None
        mock_settings.embedding_url = None
        mock_settings.embedding_model = None
        yield mock_settings

@pytest.fixture
def mock_chroma():
    with patch('kb_agent.tools.vector_tool.chromadb.PersistentClient') as mock_client_class:
        mock_client = MagicMock()
        mock_collection = MagicMock()
        
        mock_client.get_collection.return_value = mock_collection
        mock_client.get_or_create_collection.return_value = mock_collection
        mock_client_class.return_value = mock_client
        
        yield mock_collection

def test_vector_tool_similarity_conversion(mock_config, mock_chroma):
    """Test that ChromaDB distances are correctly converted to 0.0-1.0 similarities."""
    
    mock_chroma.query.return_value = {
        "ids": [["doc1", "doc2", "doc3"]],
        "distances": [[0.0, 0.4, 1.5]],
        "documents": [["content 1", "content 2", "content 3"]],
        "metadatas": [[{}, {}, {}]]
    }
    
    tool = VectorTool()
    results = tool.search("test query", threshold=0.0)
    
    assert len(results) == 3
    assert results[0]["id"] == "doc1"
    assert results[0]["score"] == 1.0
    
    assert results[1]["id"] == "doc2"
    assert round(results[1]["score"], 2) == 0.6
    
    assert results[2]["id"] == "doc3"
    assert results[2]["score"] == 0.0

def test_vector_tool_similarity_threshold_filtering(mock_config, mock_chroma):
    """Test that search correctly filters results below the similarity threshold."""
    
    mock_config.vector_score_threshold = 0.4
    
    mock_chroma.query.return_value = {
        "ids": [["doc1", "doc2", "doc3"]],
        "distances": [[0.1, 0.6000001, 0.8]],  # Similarities: 0.9, ~0.4, 0.2
        "documents": [["A", "B", "C"]],
        "metadatas": [[{}, {}, {}]]
    }
    
    tool = VectorTool()
    results = tool.search("test query")
    
    assert len(results) == 1
    assert results[0]["id"] == "doc1"
    assert round(results[0]["score"], 2) == 0.9
