## MODIFIED Requirements

### Requirement: Answer queries via Agentic RAG
The system SHALL use an iterative LangGraph-based workflow ("knowledge_base" mode) with a self-adaptive topology that includes conditional edges for fast-path routing based on query complexity, replacing the previous fixed-path 6-node flow.

#### Scenario: Chitchat query fast-path
- **WHEN** the user submits a query and `mode="knowledge_base"` and `analyze_and_route` classifies complexity as `"chitchat"`
- **THEN** the Engine routes directly to `synthesize`, bypassing `plan`, `tool_exec`, and `grade_evidence`
- **AND** the total LLM calls for this query is 2 (analyze + synthesize)

#### Scenario: Simple query fast-path
- **WHEN** the user submits a query and `mode="knowledge_base"` and `analyze_and_route` classifies complexity as `"simple"`
- **THEN** the Engine routes through `plan → tool_exec → synthesize`, bypassing `grade_evidence`
- **AND** the total LLM calls for this query is 3 (analyze + plan + synthesize)

#### Scenario: Complex query full pipeline
- **WHEN** the user submits a query and `mode="knowledge_base"` and `analyze_and_route` classifies complexity as `"complex"` or classification is unavailable
- **THEN** the Engine invokes the full pipeline: `analyze_and_route → plan → tool_exec → grade_evidence → synthesize`
- **AND** the `grade_evidence` node scores retrieved evidence and decides GENERATE, REFINE, or RE-RETRIEVE

#### Scenario: User queries a technical term requiring context
- **WHEN** the user submits a query and `mode="knowledge_base"`
- **THEN** the Engine invokes the compiled LangGraph workflow
- **AND** the workflow first analyzes query intent and complexity via `analyze_and_route`
- **AND** the workflow executes adaptive tool calls based on the routing plan
- **AND** the engine ultimately returns a synthesized answer with source citations

#### Scenario: Plan node respects routing plan in fallback paths
- **WHEN** the `plan_node` LLM response fails JSON parsing and falls back to text extraction
- **THEN** the system SHALL only extract tools that are present in `routing_plan.suggested_tools`
- **AND** the system SHALL validate each tool's applicability to the query before including it
- **AND** the system SHALL NOT call `jira_fetch`, `confluence_fetch`, or `web_fetch` unless the query contains a valid tool-specific argument pattern
