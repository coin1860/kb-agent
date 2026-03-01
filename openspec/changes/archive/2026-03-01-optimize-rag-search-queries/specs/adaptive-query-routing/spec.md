## MODIFIED Requirements

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

#### Scenario: Sub-questions drive independent tool calls
- **WHEN** `routing_plan.sub_questions` contains multiple sub-questions
- **AND** `routing_plan.suggested_tools` specifies the tools to use
- **THEN** `plan_node` SHALL generate tool calls for each sub-question independently (one tool call per sub-question × per suggested tool)
- **AND** each tool call uses the sub-question text as the query argument, NOT the original query

#### Scenario: Sub-questions contain both semantic intent and search keywords
- **WHEN** `analyze_and_route` node decomposes a query
- **THEN** each item in the `sub_questions` array SHALL be an object containing `semantic_intent` (natural language sentence) and `search_keywords` (comma or space separated exact entities/terms)
- **AND** the LLM system prompt SHALL instruct it to extract precise nouns, code symbols, and technical terms for the `search_keywords` field
