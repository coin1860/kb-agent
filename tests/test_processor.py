import pytest
from unittest.mock import patch, MagicMock
from pathlib import Path
from kb_agent.processor import Processor
from typing import Dict, Any

@patch('kb_agent.processor.VectorTool')
@patch('kb_agent.chunking.MarkdownAwareChunker')
def test_processor_process(MockChunker, MockVectorTool, tmp_path):
    # Setup mocks
    mock_vector = MagicMock()
    MockVectorTool.return_value = mock_vector
    
    mock_chunker = MagicMock()
    MockChunker.return_value = mock_chunker
    
    class FakeChunk:
        def __init__(self, text, metadata):
            self.text = text
            self.metadata = metadata
            
    # Mock chunker to return some fake chunks
    mock_chunker.chunk.return_value = [FakeChunk("Chunk 1", {"chunk_index": 0})]
    
    # Init processor
    processor = Processor(docs_path=tmp_path)
    
    # 1. Test short document (<= 2000 chars)
    short_content = "This is a short document.\n" * 10 # ~250 chars
    data_short = {
        "id": "DOC-1",
        "title": "Short Doc",
        "content": short_content,
        "metadata": {"path": "/fake/path/DOC-1.md"}
    }
    
    processor.process(data_short)
    
    # Verify file was NOT written (assuming processor doesn't write anymore)
    assert not (tmp_path / "DOC-1.md").exists()
    
    # Verify chunk was passed to chunker
    # The chunker is passed full_content starting with "# Short Doc\n\n"
    expected_full_content_short = f"# Short Doc\n\n{short_content}"
    mock_chunker.chunk.assert_called_with(expected_full_content_short, {
        "type": "chunk",
        "file_path": "/fake/path/DOC-1.md",
        "doc_id": "DOC-1",
        "related_file": "/fake/path/DOC-1.md",
        "document_title": "Short Doc",
        "path": "/fake/path/DOC-1.md"
    })
    
    # Verify added to vector tool
    mock_vector.add_documents.assert_called_once()
    mock_vector.add_documents.reset_mock()
    mock_chunker.chunk.reset_mock()
    
    # 2. Test long document (> 2000 chars)
    long_content = "This is a long document.\n" * 100 # > 2000 chars
    data_long = {
        "id": "DOC-2",
        "title": "Long Doc",
        "content": long_content,
        "metadata": {"path": "/fake/path/DOC-2.md"}
    }
    
    processor.process(data_long)
    
    # Verify file was NOT written
    assert not (tmp_path / "DOC-2.md").exists()
    
    # Verify chunk was passed to chunker WITHOUT document_summary 
    expected_full_content_long = f"# Long Doc\n\n{long_content}"
    mock_chunker.chunk.assert_called_with(expected_full_content_long, {
        "type": "chunk",
        "file_path": "/fake/path/DOC-2.md",
        "doc_id": "DOC-2",
        "related_file": "/fake/path/DOC-2.md",
        "document_title": "Long Doc",
        "path": "/fake/path/DOC-2.md"
    })
    
    mock_vector.add_documents.assert_called_once()
    
    # Since we no longer add {doc_id}-summary independently, check the ids
    kwargs = mock_vector.add_documents.call_args.kwargs
    ids = kwargs.get("ids", [])
    assert "DOC-2-chunk-0" in ids
    assert "DOC-2-summary" not in ids
