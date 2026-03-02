---
title: Indexing Pipeline
domain: ingestion
---

## MODIFIED Requirements

### Requirement: Process raw markdown files into indexable formats
The system SHALL ingest files from a local source directory, save a standardized copy using the file's stem name (without original extension), and generate a concise LLM summary for each file.

#### Scenario: User runs kb-agent index on valid local directory
- **WHEN** the user runs the `kb-agent index` command
- **THEN** the system iterates through all files in the configured `source_docs_path`
- **AND** the system generates an LLM summary for each file
- **AND** the system saves both the full content and the summary to the `index_path`
- **AND** the document ID SHALL be derived from the file's stem (`Path.stem`) not the full filename (`Path.name`)
- **AND** a source file `report.docx` SHALL produce `index/report.md` and `index/report-summary.md`, NOT `index/report.docx.md`

#### Scenario: ChromaDB metadata stores correct index paths
- **WHEN** a document is indexed into ChromaDB
- **THEN** the `file_path` and `related_file` metadata fields SHALL point to the index-path `.md` file using the stem-based name
- **AND** the path SHALL be resolvable by the `read_file` tool
