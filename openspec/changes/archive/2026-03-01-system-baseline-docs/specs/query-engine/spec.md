## ADDED Requirements

### Requirement: Answer queries via Normal chat mode
The system SHALL support a standard conversational mode ("normal") that directly streams user input to the LLM without augmenting it via the agentic workflow.

#### Scenario: User queries the engine in normal mode
- **WHEN** the `Engine.answer_query` is called with `mode="normal"`
- **THEN** the system bypasses the retrieval pipeline
- **AND** the system returns a direct LLM response using the provided chat history

### Requirement: Answer queries via Agentic RAG
The system SHALL use an iterative LangGraph-based workflow ("knowledge_base" mode) to dynamically search the vector database, knowledge graph, or filesystem to answer complex user questions.

#### Scenario: User queries a technical term requiring context
- **WHEN** the user submits a query and `mode="knowledge_base"`
- **THEN** the Engine invokes the compiled LangGraph workflow
- **AND** the workflow executes iterative tool calls (like VectorTool or GraphTool) until sufficient context is gathered
- **AND** the engine ultimately returns an synthesized answer using the retrieved context

### Requirement: Automatic web URL resolution
The system SHALL intercept HTTP URLs in user queries, fetch their content, and use it as ad-hoc context to answer the user's question, bypassing the standard RAG or local index database.

#### Scenario: Query contains a URL
- **WHEN** the user provides the query "Summarize this page https://example.com/spec"
- **THEN** the system detects the URL via regex
- **AND** the system fetches the web content
- **AND** the system optionally processes it into the index if in knowledge_base mode
- **AND** the system answers the user's implicit or explicit question using only that fetched content
