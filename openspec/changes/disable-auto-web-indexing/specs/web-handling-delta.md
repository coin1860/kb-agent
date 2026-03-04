## MODIFIED Requirements

### Requirement: Disable Automatic Ingestion on Query
When a URL is detected in a user query, the system shall fetch and use the content to answer the question, but shall not save or index the content into the permanent knowledge base automatically.

#### Scenario: User pastes a URL and asks a question
- **WHEN** the user provided query contains one or more URLs
- **AND** the system is in Knowledge Base (RAG) mode
- **THEN** the system shall fetch the URL content
- **AND** use the content to generate an answer
- **AND** DO NOT call the indexing processor to store the content in Chroma DB or the files database.
