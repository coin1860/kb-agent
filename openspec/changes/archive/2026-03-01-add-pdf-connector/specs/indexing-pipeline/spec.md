## ADDED Requirements

### Requirement: Local File Scan Includes PDF
The `LocalFileConnector` must treat `.pdf` as a natively supported document type alongside markdown, text, word, and spreadsheets during local directory scanning.

#### Scenario: User queries for files in local directory
- **WHEN** the `fetch_all` or `fetch_data` method is invoked
- **THEN** files ending with `.pdf` (case-insensitive) should be discovered and processed.

### Requirement: Large PDF Text Extraction with Pagination Structure
The system must be capable of extracting the raw text content from PDF documents, specifically handling large files natively without memory corruption, outputting a structure compatible with downstream Markdown Chunkers.

#### Scenario: A Large PDF file is processed
- **WHEN** a `.pdf` file is passed to `_read_file`
- **THEN** it must utilize PyMuPDF (fitz) to extract text safely.
- **AND** it must inject explicit Structural Metadata (e.g. `## Page N`) between text segments so that the `MarkdownAwareChunker` correctly separates large PDF files into bite-sized indexable chunks using standard Header boundaries.

### Requirement: Robust PDF Processing Tests
The new functionality must be backed by explicit testing bounds.

#### Scenario: Running test suite
- **WHEN** `pytest tests/` is invoked
- **THEN** it must execute a test isolating `LocalFileConnector` PDF reading behavior, verifying that generated markdown accurately represents the injected pagination.
