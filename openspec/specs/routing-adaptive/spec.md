---
title: Adaptive Query Routing
domain: routing
---

# adaptive-query-routing Specification

## Purpose
Intelligent query intent classification and decomposition to optimize retrieval tool selection.
## Requirements
### Requirement: Classify query intent before retrieval
The system SHALL analyze each incoming query using a lightweight LLM decompose call on the first iteration. URL detection remains rule-based (pre-decompose guard). Jira ticket detection is handled by the LLM decompose step rather than hardcoded regex. The LLM planner is only used on retry rounds when decompose is not applicable.

#### Scenario: First-round routing with LLM decompose
- **WHEN** `plan_node` is invoked with `iteration == 0` and no existing context
- **THEN** the system SHALL first check for URL patterns using regex (fast-path guard)
- **AND** if no URL is found, the system SHALL invoke the `_decompose_query` LLM call
- **AND** the LLM decompose call SHALL determine whether to:
  - Decompose into 3 sub-queries for parallel `vector_search` (most common case)
  - Route directly to a specific tool (e.g., `jira_fetch` for ticket IDs)
- **AND** Jira ticket detection SHALL be performed by the LLM, not by regex pattern matching

#### Scenario: URL fast-path guard (pre-decompose)
- **WHEN** `plan_node` is invoked with `iteration == 0` and the query contains a valid HTTP/HTTPS URL
- **THEN** the system SHALL route directly to `web_fetch` without invoking the decompose LLM call
- **AND** this check SHALL occur before the LLM decompose step

#### Scenario: Retry-round LLM-based planning
- **WHEN** `plan_node` is invoked with `iteration >= 1` or existing context
- **THEN** the system SHALL use the existing LLM planner with full tool descriptions
- **AND** the planner SHALL be given the file paths, ticket IDs, and page references extracted from previous round results
- **AND** the planner prompt SHALL strongly guide toward following discovered clues (read_file, jira_fetch, confluence_fetch) rather than rephrasing vector searches

#### Scenario: Exact keyword query (ticket ID, config name)
- **WHEN** the user submits a query containing a specific identifier (e.g., "PROJ-123", "KB_AGENT_MAX_ITERATIONS")
- **THEN** the system classifies the query as `exact`
- **AND** the system routes primarily to `jira_fetch` (for Jira keys) or `vector_search` (for other identifiers)

#### Scenario: Conceptual or fuzzy query
- **WHEN** the user submits a conceptual question (e.g., "how does the indexing pipeline work?")
- **THEN** the system routes to `vector_search` on the first round

#### Scenario: File discovery query
- **WHEN** the user asks to find or list files (e.g., "查找关于认证的文件")
- **THEN** the system routes to `vector_search` (since `local_file_qa` is deprecated from ALL_TOOLS)
- **AND** the LLM synthesizer SHALL format results as a file list when the intent is file discovery

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

### Requirement: Output structured routing plan
The system SHALL produce a structured routing plan as JSON containing `query_type`, `complexity`, `sub_questions`, `suggested_tools`, and optional `grep_keywords`.

#### Scenario: Routing plan generation
- **WHEN** the `analyze_and_route` node completes analysis
- **THEN** the output contains a valid JSON object with fields: `query_type` (string, one of `exact`, `conceptual`, `relational`, `file_discovery`, `chitchat`), `complexity` (string, one of `simple`, `complex`, `chitchat`), `sub_questions` (array), `suggested_tools` (array), `grep_keywords` (array or empty)
- **AND** the routing plan is stored in `AgentState.routing_plan`

