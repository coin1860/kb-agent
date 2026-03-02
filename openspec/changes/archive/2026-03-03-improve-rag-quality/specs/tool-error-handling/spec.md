---
title: Tool Error Handling
domain: retrieval
---

## ADDED Requirements

### Requirement: Detect and filter error results from context
The `tool_node` SHALL detect tool/connector error responses and exclude them from the evidence context to prevent the LLM from synthesizing answers based on error messages.

#### Scenario: Connector returns error with metadata flag
- **WHEN** a tool returns a JSON result where any item has `metadata.error == True`
- **THEN** the `tool_node` SHALL NOT add the result to `AgentState.context`
- **AND** the `tool_node` SHALL log the error in `tool_history` with an `error: True` marker
- **AND** the `tool_node` SHALL emit a warning status message (e.g., `⚠️ jira_fetch returned error`)

#### Scenario: Connector returns error as dict with status field
- **WHEN** a tool returns a JSON dict with `status: "error"`
- **THEN** the `tool_node` SHALL NOT add the result to `AgentState.context`
- **AND** the `tool_node` SHALL log the error in `tool_history` with an `error: True` marker

#### Scenario: Non-error result passes through normally
- **WHEN** a tool returns a result without error markers
- **THEN** the `tool_node` SHALL add it to context as before (existing behavior)

### Requirement: Explicit no-results feedback for search tools
Search tools SHALL return a structured "no results" response instead of empty arrays, so the LLM can understand that the search found nothing.

#### Scenario: vector_search returns empty results
- **WHEN** `vector_search` finds no chunks above the score threshold
- **THEN** the tool SHALL return a JSON object with `status: "no_results"`, `tool: "vector_search"`, and a human-readable message
- **AND** the message SHALL suggest trying different keywords

#### Scenario: graph_related returns empty results
- **WHEN** `graph_related` finds no related entities for the given ID
- **THEN** the tool SHALL return a JSON object with `status: "no_results"` and a descriptive message
