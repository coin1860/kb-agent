## ADDED Requirements

### Requirement: Classify query intent before retrieval
The system SHALL analyze each incoming query and classify it into one of four intent types: `exact`, `conceptual`, `relational`, or `file_discovery`, before selecting retrieval tools.

#### Scenario: Exact keyword query (ticket ID, config name)
- **WHEN** the user submits a query containing a specific identifier (e.g., "PROJ-123", "KB_AGENT_MAX_ITERATIONS")
- **THEN** the system classifies the query as `exact`
- **AND** the system routes primarily to `grep_search` with the identifier as keyword

#### Scenario: Conceptual or fuzzy query
- **WHEN** the user submits a conceptual question (e.g., "how does the indexing pipeline work?")
- **THEN** the system classifies the query as `conceptual`
- **AND** the system routes primarily to `vector_search` or `hybrid_search`

#### Scenario: Relational or comparison query
- **WHEN** the user asks about relationships between entities (e.g., "what tickets are linked to PROJ-100?")
- **THEN** the system classifies the query as `relational`
- **AND** the system routes primarily to `graph_related` followed by `read_file`

#### Scenario: File discovery query
- **WHEN** the user asks to find or list files (e.g., "查找关于认证的文件")
- **THEN** the system classifies the query as `file_discovery`
- **AND** the system routes to `local_file_qa`

### Requirement: Decompose complex queries into sub-questions
The system SHALL decompose multi-part or complex queries into atomic sub-questions, each retrievable independently.

#### Scenario: Multi-part question
- **WHEN** the user submits "Compare the indexing pipeline with the query engine and list their shared dependencies"
- **THEN** the system decomposes into at least two sub-questions (e.g., "indexing pipeline architecture", "query engine architecture", "shared dependencies")
- **AND** each sub-question is routed and retrieved independently
- **AND** results are merged before synthesis

#### Scenario: Simple single-intent question
- **WHEN** the user submits a simple question (e.g., "What is VectorTool?")
- **THEN** the system does NOT decompose and proceeds with a single retrieval pass

### Requirement: Output structured routing plan
The system SHALL produce a structured routing plan as JSON containing `query_type`, `sub_questions`, `suggested_tools`, and optional `grep_keywords`.

#### Scenario: Routing plan generation
- **WHEN** the `analyze_and_route` node completes analysis
- **THEN** the output contains a valid JSON object with fields: `query_type` (string), `sub_questions` (array), `suggested_tools` (array), `grep_keywords` (array or empty)
- **AND** the routing plan is stored in `AgentState.routing_plan`
