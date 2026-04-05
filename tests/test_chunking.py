import pytest
from kb_agent.chunking import MarkdownAwareChunker

def test_contextual_prefix_chunking():
    chunker = MarkdownAwareChunker(max_chars=1000, overlap_chars=200)
    
    # Simple markdown with 1 section
    text = "## Getting Started\nThis is a short chunk."
    metadata = {
        "document_title": "Guide",
        "document_summary": "A short guide."
    }
    
    chunks = chunker.chunk(text, metadata)
    
    # Should be 1 chunk
    assert len(chunks) == 1
    chunk = chunks[0]
    
    # Check if the prefix is prepended correctly
    expected_prefix = (
        "Document: Guide\n"
        "Section: Getting Started\n"
        "Summary: A short guide.\n\n"
    )
    
    assert chunk.text.startswith(expected_prefix)
    assert chunk.text.endswith("This is a short chunk.")
    
    # Also check without summary
    metadata_no_summary = {
        "document_title": "Guide"
    }
    chunks2 = chunker.chunk(text, metadata_no_summary)
    
    expected_prefix_2 = (
        "Document: Guide\n"
        "Section: Getting Started\n\n"
    )
    
    assert chunks2[0].text.startswith(expected_prefix_2)
