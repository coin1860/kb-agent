## ADDED Requirements

### Requirement: Classify query complexity for pipeline routing
The system SHALL classify each query's complexity as `chitchat`, `simple`, or `complex` within the `analyze_and_route` node, alongside existing intent classification, at zero additional LLM cost.

#### Scenario: Chitchat greeting detected
- **WHEN** the user submits a social or greeting query (e.g., "你好", "谢谢", "你是谁")
- **THEN** the system sets `routing_plan.complexity` to `"chitchat"`
- **AND** the system sets `query_type` to `"chitchat"`

#### Scenario: Simple single-intent query detected
- **WHEN** the user submits a single-intent knowledge query with no sub-questions (e.g., "VectorTool 是什么", "PROJ-123 详情")
- **THEN** the system sets `routing_plan.complexity` to `"simple"`
- **AND** `sub_questions` is an empty array

#### Scenario: Complex multi-intent query detected
- **WHEN** the user submits a multi-part or comparison query requiring decomposition (e.g., "比较索引管线和查询引擎的架构差异")
- **THEN** the system sets `routing_plan.complexity` to `"complex"`
- **AND** `sub_questions` contains at least two items

### Requirement: Chitchat queries bypass the RAG pipeline
The system SHALL route `chitchat` queries directly from `analyze_and_route` to `synthesize`, skipping `plan`, `tool_exec`, and `grade_evidence` nodes entirely.

#### Scenario: Chitchat short-circuit
- **WHEN** `routing_plan.complexity` equals `"chitchat"`
- **THEN** the graph routes directly from `analyze_and_route` to `synthesize`
- **AND** no tool calls are made
- **AND** `synthesize` responds in conversational mode without the "only from evidence" constraint

#### Scenario: Chitchat audit logging
- **WHEN** a chitchat short-circuit is triggered
- **THEN** the system logs `fast_path_hit` via `log_audit` with `path_type: "chitchat"`

### Requirement: Simple queries skip evidence grading
The system SHALL route `simple` queries directly from `tool_exec` to `synthesize`, skipping the `grade_evidence` node.

#### Scenario: Simple query skips grading
- **WHEN** `routing_plan.complexity` equals `"simple"` and tool execution completes
- **THEN** the graph routes from `tool_exec` directly to `synthesize`
- **AND** the `grade_evidence` node is not invoked

#### Scenario: Simple skip audit logging
- **WHEN** a simple skip is triggered
- **THEN** the system logs `fast_path_hit` via `log_audit` with `path_type: "simple_skip_grading"`

### Requirement: Complex queries follow the full pipeline
The system SHALL route `complex` queries through the complete pipeline including `grade_evidence`.

#### Scenario: Complex query full pipeline
- **WHEN** `routing_plan.complexity` equals `"complex"` or is unset/unknown
- **THEN** the graph follows the existing full path: `plan → tool_exec → grade_evidence → synthesize`
