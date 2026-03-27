## MODIFIED Requirements

### Requirement: Answer queries via Agentic RAG
The system SHALL use an iterative LangGraph-based workflow ("knowledge_base" mode) with a self-adaptive topology that includes conditional edges for fast-path routing based on query complexity, replacing the previous fixed-path 6-node flow. The `tool_node` MUST encapsulate JSON array results from tools like `vector_search` into individual context items rather than a single merged string, ensuring the `grade_evidence_node` correctly evaluates each chunk. For queries explicitly requesting analysis, reading, or querying of a `.csv` file, the `analyze_and_route` node MUST bypass vector search decomposition and output a `"direct"` action to invoke the `csv_query` tool with the extracted filename and user question.

This same RAG graph SHALL also serve as the backend for CLI mode's `free_agent` queries. The graph is entry-mode agnostic — callers (TUI or CLI) construct an `AgentState` and invoke the compiled graph; the graph does not distinguish between entry points.

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

#### Scenario: CLI free_agent query invokes same RAG graph
- **WHEN** a user enters a query in kb-cli
- **AND** `route_intent()` returns `free_agent`
- **THEN** `SkillShell._run_rag_query()` SHALL invoke the compiled RAG graph with an `AgentState` containing `query`, `messages`, and `status_callback`
- **AND** the graph SHALL execute with the same logic as TUI mode

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

#### Scenario: Vector search returns multiple chunks
- **WHEN** the `tool_node` executes `vector_search` which returns 5 chunks
- **THEN** the `tool_node` appends 5 distinct formatted items to `new_context`
- **AND** the `grade_evidence_node` receives all 5 items and properly triggers the LLM grading (since 5 > auto_approve_max_items).

#### Scenario: Direct routing for CSV queries
- **WHEN** the user explicitly asks to query, analyze, or read a `.csv` file (e.g., "query dataset.csv for users over 30")
- **THEN** the `analyze_and_route` node MUST classify the action as `"direct"`
- **AND** route to the `csv_query` tool, extracting the filename and the specific question without decomposing into vector search queries
