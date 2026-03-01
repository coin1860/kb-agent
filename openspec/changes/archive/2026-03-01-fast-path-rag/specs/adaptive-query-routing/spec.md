## MODIFIED Requirements

### Requirement: Output structured routing plan
The system SHALL produce a structured routing plan as JSON containing `query_type`, `complexity`, `sub_questions`, `suggested_tools`, and optional `grep_keywords`.

#### Scenario: Routing plan generation
- **WHEN** the `analyze_and_route` node completes analysis
- **THEN** the output contains a valid JSON object with fields: `query_type` (string, one of `exact`, `conceptual`, `relational`, `file_discovery`, `chitchat`), `complexity` (string, one of `simple`, `complex`, `chitchat`), `sub_questions` (array), `suggested_tools` (array), `grep_keywords` (array or empty)
- **AND** the routing plan is stored in `AgentState.routing_plan`

### Requirement: Classify query intent before retrieval
The system SHALL analyze each incoming query and classify it into one of five intent types: `exact`, `conceptual`, `relational`, `file_discovery`, or `chitchat`, before selecting retrieval tools.

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

#### Scenario: Chitchat or greeting query
- **WHEN** the user submits a social, greeting, or non-knowledge query (e.g., "你好", "谢谢")
- **THEN** the system classifies the query as `chitchat`
- **AND** `suggested_tools` is an empty array
