## ADDED Requirements

### Requirement: Conditional LLM Summarization
The system SHALL only generate an overarching document summary using the LLM if the raw plaintext content of the document is strictly greater than 2000 characters.

#### Scenario: Summarizing large documents
- **WHEN** a document with length > 2000 characters is processed
- **THEN** the system generates an LLM summary of the document.

#### Scenario: Skipping summary for short documents
- **WHEN** a document with length <= 2000 characters is processed
- **THEN** the system skips generating a summary via the LLM.

### Requirement: Direct Memory Processing
The system SHALL NOT automatically save incoming document data directly to a `.md` disk file during generic data processing, deferring to the document's original state or preserving it merely in memory for ingestion mapping, unless explicitly mandated.

#### Scenario: Avoid writing cached MD copies
- **WHEN** the `Processor` receives an incoming structured document extraction
- **THEN** the system performs chunking and embedding directly from the content buffer without caching a disk copy inside the `.chroma` indexing path.

## REMOVED Requirements

### Requirement: Independent Summary Indexing
**Reason**: Replaced by direct contextual injection inside individual chunks, saving vector database overhead and minimizing loose semantics.
**Migration**: Existing indices must be thoroughly rebuilt. The application logic no longer adds distinct metadata records equipped uniformly with `{doc_id}-summary`.
