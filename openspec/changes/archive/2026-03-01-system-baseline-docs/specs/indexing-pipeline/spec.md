## ADDED Requirements

### Requirement: Process raw markdown files into indexable formats
The system SHALL ingest markdown files from a local source directory, save a standardized copy, and generate a concise LLM summary for each file.

#### Scenario: User runs kb-agent index on valid local directory
- **WHEN** the user runs the `kb-agent index` command
- **THEN** the system iterates through all files in the configured `source_docs_path`
- **AND** the system generates an LLM summary for each file
- **AND** the system saves both the full content and the summary to the `index_path`

### Requirement: Vectorize document content
The system SHALL chunk and embed both the full content (truncated) and the summary of a document into ChromaDB to enable semantic search.

#### Scenario: Document is processed by VectorTool
- **WHEN** a document and its generated summary are ready for indexing
- **THEN** the system adds the summary to ChromaDB with type `summary`
- **AND** the system adds the truncated full content to ChromaDB with type `full`

### Requirement: Archive processed documents
The system SHALL move successfully processed source documents out of the input directory to prevent duplicate processing on subsequent runs.

#### Scenario: File completes indexing successfully
- **WHEN** a document has been successfully summary-generated and vectorized
- **THEN** the system moves the physical file from `source_docs_path` to `archive_path`

### Requirement: Build Semantic Knowledge Graph
The system SHALL parse explicit relationships (like Jira IDs and local markdown links) from the documents and construct a directed Knowledge Graph.

#### Scenario: GraphBuilder scans the index
- **WHEN** the indexing pipeline finishes processing documents
- **THEN** the `GraphBuilder` parses the files in the `index_path` for `[JIRA-123]` tags and `[Link](file)` patterns
- **AND** the system outputs a `knowledge_graph.json` file representing the graph nodes and edges
