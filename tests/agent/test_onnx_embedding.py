import os
import pytest
from pathlib import Path
from tempfile import TemporaryDirectory

import chromadb
from kb_agent.tools.vector_tool import ONNXEmbeddingFunction, VectorTool
from kb_agent.config import Settings
import kb_agent.config as config

def test_onnx_embedding_function(monkeypatch):
    """
    Test the ONNXEmbeddingFunction directly if the model directory exists.
    User's model path: /Users/shaneshou/Dev/Data/bge-small-zh-v1.5
    """
    model_dir = "/Users/shaneshou/Dev/Data/bge-small-zh-v1.5"
    if not os.path.exists(model_dir):
        pytest.skip(f"Test model directory {model_dir} not found.")
        
    embedding_fn = ONNXEmbeddingFunction(model_dir)
    
    # Test with a simple sentence
    documents = ["你好，世界！", "This is a test document."]
    embeddings = embedding_fn(documents)
    
    # Check output
    assert embeddings is not None
    assert len(embeddings) == 2
    
    # Check dimensionality (BGE small should be 512)
    assert len(embeddings[0]) == 512
    assert len(embeddings[1]) == 512

def test_vector_tool_fallback_logic(monkeypatch):
    """Test that the configuration fallback logic initializes the correct function"""
    model_dir = "/Users/shaneshou/Dev/Data/bge-small-zh-v1.5"
    if not os.path.exists(model_dir):
        pytest.skip(f"Test model directory {model_dir} not found.")
        
    with TemporaryDirectory() as tmpdir:
        # Mock settings to use Local ONNX
        test_settings = Settings(
            embedding_url=None,
            embedding_model_path=Path("/Users/shaneshou/Dev/Data"),
            embedding_model="bge-small-zh-v1.5",
            data_folder=Path(tmpdir)
        )
        monkeypatch.setattr(config, "settings", test_settings)
        
        tool = VectorTool("test_collection")
        
        # Verify the embedding function used by adding and querying
        tool.add_documents(["测试向量数据库的一句话"], [{"test": "meta"}], ["id1"])
        
        results = tool.search("向量", n_results=1, threshold=0.99)
        assert len(results) == 1
        assert results[0]["id"] == "id1"
