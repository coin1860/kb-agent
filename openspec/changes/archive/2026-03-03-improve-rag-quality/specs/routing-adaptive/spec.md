---
title: Adaptive Query Routing
domain: routing
---

## MODIFIED Requirements

### Requirement: Classify query intent before retrieval
The system SHALL analyze each incoming query using lightweight rules (not LLM) on the first iteration, falling back to LLM-based planning only on retry rounds.

#### Scenario: First-round rule-based routing (default to vector_search)
- **WHEN** `plan_node` is invoked with `iteration == 0` and no existing context
- **THEN** the system SHALL skip the LLM planner call entirely
- **AND** the system SHALL apply rule-based tool selection:
  - If query contains a valid URL (`https?://...`) → `web_fetch`
  - If query contains a Jira key pattern (`[A-Z]+-\d+`) → `jira_fetch`
  - Otherwise → `vector_search` with the original query as-is
- **AND** no LLM API call SHALL be made for this planning step

#### Scenario: Retry-round LLM-based planning
- **WHEN** `plan_node` is invoked with `iteration >= 1` or existing context
- **THEN** the system SHALL use the existing LLM planner with full tool descriptions
- **AND** the planner SHALL be informed of previous attempts and their results

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
