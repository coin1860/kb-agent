## MODIFIED Requirements

### Requirement: Answer queries via Agentic RAG
The system SHALL use an iterative LangGraph-based workflow ("knowledge_base" mode) to dynamically search the vector database, knowledge graph, local file qa tool, or filesystem to answer complex user questions.

#### Scenario: User queries a technical term requiring context
- **WHEN** the user submits a query and `mode="knowledge_base"`
- **THEN** the Engine invokes the compiled LangGraph workflow
- **AND** the workflow executes iterative tool calls (like VectorTool, GraphTool, or LocalFileQATool) until sufficient context is gathered
- **AND** the engine ultimately returns an synthesized answer using the retrieved context

## ADDED Requirements

### Requirement: Contextual File Q&A
The planner agent SHALL be able to explicitly resolve an index number (e.g., "1") to a specific filename when the user asks a follow-up question based on the `LocalFileQATool`'s table output.

#### Scenario: User asks to summarize file 1
- **WHEN** the user says "Summarize file 1"
- **AND** the conversation history contains a `LocalFileQATool` result table
- **THEN** the planner agent looks up the filename corresponding to index `1`
- **AND** the planner agent calls the `read_file` tool with that specific filename
- **AND** the synthesizer returns a summary based strictly on that file
