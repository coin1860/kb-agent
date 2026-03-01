## Context

Currently, the `LocalFileConnector` in `kb_agent` processes local directories to find knowledge documents. It converts discovered files to text strings, which the pipeline then chunks, summarizes, and indexes into ChromaDB.
However, it currently ignores `.pdf` parsing. Given that most enterprise or complex documents exist as PDFs (often containing thousands of pages), the system is missing critical data ingestion capability. Treating a 1000-page PDF as a single in-memory string is computationally unstable and undermines the downstream Map-Reduce and semantic chunker limits.

## Goals / Non-Goals

**Goals:**
- Extract pure text reliably from PDF documents using Python.
- Handle extremely large PDF files (e.g., thousands of pages) by utilizing a stable iteration Strategy avoiding out-of-memory overheads.
- Pass chunked bounds clearly from `LocalFileConnector` into the downstream `SemanticChunker` structure format without overflowing.
- Ensure end-to-end integration mapping from extraction -> indexing -> query works efficiently for PDF sources. Include explicit unit/integration testing limits.

**Non-Goals:**
- **OCR (Optical Character Recognition)**: We will not attempt to extract text from scanned image-based PDFs in this iteration to keep dependencies light and speeds high.
- **Complex Layout Preservation**: We won't attempt to perfectly reconstruct complex multi-column floating layouts or vector graphics into Markdown. Text stripping is sufficient.

## Decisions

1. **Dependency Choice: `PyMuPDF` (fitz)**
   - *Rationale:* PyMuPDF is widely regarded as the fastest and most reliable PDF text extraction library in Python. It parses the document tree safely and reads page by page.
   
2. **Handling Large Document Splitting (Pagination Chunking Strategy):**
   - Instead of trying to parse out Markdown Headers from PDFs (which are unreliable to guess), we will use **Physical Pages** as our primary bounding box for large PDFs.
   - The `_read_pdf` method will not just return one monolithic string. It will yield text blocks *per page* (or per N pages), wrapping each chunk in explicit Markdown structure like:
     `## Page X`
   - If a page itself exceeds the `SemanticChunker`'s 4000 character limits, the downstream `split_by_paragraphs` fallback within the Chunker will elegantly slice the page into valid overlaps.
   - This maintains 100% compatibility with our newly implemented `MarkdownAwareChunker`—the chunker will see `## Page X` as a Markdown header and perfectly slice the massive PDF into Section representations without crashing.

3. **Writing Tests:**
   - Establish dedicated `test_local_file.py` and `test_pdf_integration.py` tests. We will use a mockup PDF via `PyMuPDF` or synthetic generation to assert that a 100-page simulated PDF is lazily resolved without crashing the Map-Reduce summaries.

## Risks / Trade-offs

- **Image-based PDFs**: Users might upload PDFs that are just scanned images. `PyMuPDF`'s standard text extraction will return empty strings for these.
- **Header Parsing Noise**: PDF Page headers/footers (page numbers, titles) will be interleaved into the text. We trade off clean layout sanitization for immediate searchability.
