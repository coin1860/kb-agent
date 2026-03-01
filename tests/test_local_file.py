import pytest
from pathlib import Path
from kb_agent.connectors.local_file import LocalFileConnector

def create_mock_pdf(path: Path):
    """Creates a basic multipage PDF using PyMuPDF for testing."""
    import fitz
    
    doc = fitz.open()
    
    # Page 1
    page1 = doc.new_page()
    page1.insert_text(fitz.Point(50, 50), "This is the first page of the PDF.")
    
    # Page 2
    page2 = doc.new_page()
    page2.insert_text(fitz.Point(50, 50), "This is the second page. It has more content.")
    
    doc.save(path)
    doc.close()

def test_pdf_extraction_structural_boundaries(tmp_path: Path):
    """
    Tests that a multipage PDF is correctly loaded by LocalFileConnector
    and that `## Page N` boundaries are successfully injected for the semantic chunker.
    """
    source_dir = tmp_path / "source"
    source_dir.mkdir()
    
    pdf_path = source_dir / "test_document.pdf"
    create_mock_pdf(pdf_path)
    
    connector = LocalFileConnector(source_dir)
    results = connector.fetch_all()
    
    # Assert discovery
    assert len(results) == 1
    assert results[0]["id"] == "test_document.pdf"
    
    # Assert metadata
    assert results[0]["metadata"]["type"] == ".pdf"
    
    # Assert structural content extraction (Markdown Bounding Hooks)
    content = results[0]["content"]
    assert content is not None
    
    assert "## Page 1" in content
    assert "This is the first page of the PDF." in content
    assert "## Page 2" in content
    assert "This is the second page. It has more content." in content
    
    # Ensure they are separated cleanly
    assert content.count("## Page") == 2
