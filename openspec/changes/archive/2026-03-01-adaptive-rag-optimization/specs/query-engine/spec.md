## MODIFIED Requirements

### Requirement: Answer queries via Agentic RAG
The system SHALL use an iterative LangGraph-based workflow ("knowledge_base" mode) with a 6-node self-adaptive topology: `analyze_and_route → plan → tool_exec → grade_evidence → synthesize`, replacing the previous 4-node linear flow.

#### Scenario: User queries a technical term requiring context
- **WHEN** the user submits a query and `mode="knowledge_base"`
- **THEN** the Engine invokes the compiled LangGraph workflow
- **AND** the workflow first analyzes query intent via `analyze_and_route`
- **AND** the workflow executes adaptive tool calls based on the routing plan
- **AND** the `grade_evidence` node scores retrieved evidence and decides GENERATE, REFINE, or RE-RETRIEVE
- **AND** the engine ultimately returns a synthesized answer with source citations

## ADDED Requirements

### Requirement: Generate answers with source citations
The system SHALL include source citations in the synthesized answer, referencing the file path and line number of each piece of evidence used.

#### Scenario: Answer with inline citations
- **WHEN** the `synthesize` node generates an answer from graded evidence
- **THEN** the answer includes numbered footnote references inline (e.g., `[1]`, `[2]`)
- **AND** a citation footer is appended listing each source: `[N] /path/to/file.md:L42`

#### Scenario: Evidence without line number metadata
- **WHEN** a context item comes from `vector_search` and lacks a specific line number
- **THEN** the citation references only the file path without line number (e.g., `[N] /path/to/file.md`)

#### Scenario: No evidence available for synthesis
- **WHEN** the `synthesize` node has no context items (all filtered or empty)
- **THEN** the system responds with "I couldn't find relevant information in the knowledge base to answer this question."
- **AND** no citation footer is appended
