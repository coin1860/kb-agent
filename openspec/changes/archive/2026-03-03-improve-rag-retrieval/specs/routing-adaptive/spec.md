---
title: Adaptive Query Routing
domain: routing
---

# routing-adaptive Delta Spec

## MODIFIED Requirements

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
