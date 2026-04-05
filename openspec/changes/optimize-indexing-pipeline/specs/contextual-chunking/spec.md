## ADDED Requirements

### Requirement: Inject Document Context Prefix
The system SHALL inject a prefix containing context from the parent document into each processed text chunk before saving to the vector store.

#### Scenario: Prepending document metadata to chunk
- **WHEN** the `MarkdownAwareChunker` outputs split document blocks
- **THEN** it formats the chunks using a deterministic template capturing the Document title, the Section title, and any LLM Summary (if successfully generated).

#### Scenario: Handling short documents without summary
- **WHEN** a document chunk is generated and the document had no generated summary (e.g. length <= 2000)
- **THEN** the injected prefix omits the summary section gracefully.
