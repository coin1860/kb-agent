## 1. Dependencies and Setup

- [x] 1.1 Add `PyMuPDF` (package: `pymupdf`) to project dependencies in `pyproject.toml` and sync the lockfile using `uv add pymupdf`.

## 2. Local File Connector Implementation

- [x] 2.1 Update `src/kb_agent/connectors/local_file.py` to import `fitz` exclusively inside the new method (with try/except fallback).
- [x] 2.2 Add `_read_pdf(self, file_path: Path) -> str` method. It MUST explicitly write Markdown Headers representing structural bounds per page (e.g., `## Page {page_num}`).
- [x] 2.3 Modify `fetch_all` in `LocalFileConnector` to include `*.pdf` in the Glob scanning patterns.
- [x] 2.4 Modify `_read_file` to route `.pdf` file suffixes to the newly created `_read_pdf` method.

## 3. Large Document Structural Integration & Testing

- [x] 3.1 Create/Modify tests in `tests/test_local_file.py` to generate a mocked multi-page PDF locally.
- [x] 3.2 Add a unit test verifying `LocalFileConnector._read_pdf` generates text containing `## Page N` headers, thereby proving Large File Pagination mappings.
- [x] 3.3 Validate the entire indexing pipeline manually or via tests against `.pdf` drops into the source directory.
