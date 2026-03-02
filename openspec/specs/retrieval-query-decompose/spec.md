---
title: Query Decomposition for Retrieval
domain: retrieval
---

# retrieval-query-decompose Specification

## Purpose
LLM-based query decomposition into sub-queries for parallel vector search on the first retrieval round, improving recall by casting a wider net.

## Requirements

### Requirement: Decompose user query into sub-queries on first iteration
The system SHALL use a lightweight LLM call to decompose the user's question into 3 sub-queries for parallel vector search when no faster routing rule (URL, Jira) applies.

#### Scenario: Standard knowledge base question
- **WHEN** `plan_node` is invoked with `iteration == 0` and no existing context
- **AND** the query does not contain a URL or an obvious Jira/tool-specific intent
- **THEN** the system SHALL invoke the LLM with a decompose prompt to produce exactly 3 sub-queries
- **AND** the system SHALL emit one `vector_search` tool call per sub-query (3 total)
- **AND** the original user query text SHALL NOT be used directly as a vector_search query

#### Scenario: URL detected — skip decomposition
- **WHEN** `plan_node` is invoked with `iteration == 0` and the query contains a valid HTTP/HTTPS URL
- **THEN** the system SHALL route directly to `web_fetch` without invoking the decompose LLM call

#### Scenario: Jira/tool intent detected by LLM — skip decomposition
- **WHEN** `plan_node` is invoked with `iteration == 0` and the LLM decompose step determines the query is about a specific Jira ticket or requires a specific tool
- **THEN** the system SHALL return the appropriate single tool call (e.g., `jira_fetch`)
- **AND** the system SHALL NOT generate sub-queries for vector search

#### Scenario: Decompose prompt format
- **WHEN** the decompose LLM call is invoked
- **THEN** the prompt SHALL instruct the LLM to output a JSON object with either:
  - `{"action": "decompose", "sub_queries": ["q1", "q2", "q3"]}` for vector search decomposition
  - `{"action": "direct", "tool": "<tool_name>", "args": {...}}` for direct tool routing (e.g., Jira, web_fetch)
- **AND** the LLM SHALL be instructed to detect Jira-style ticket IDs (e.g., FSR-123, WCL-123, PROJ-456) without relying on hardcoded regex patterns

### Requirement: Deduplicate chunks from parallel sub-queries
The system SHALL deduplicate context items when multiple vector_search calls return overlapping chunks.

#### Scenario: Duplicate chunks from different sub-queries
- **WHEN** multiple `vector_search` calls in a single tool_node execution return chunks with the same chunk ID
- **THEN** the system SHALL keep only one copy of each unique chunk (by ID)
- **AND** the system SHALL retain the copy with the highest relevance score

#### Scenario: No duplicates
- **WHEN** multiple `vector_search` calls return entirely distinct chunks
- **THEN** all chunks SHALL be preserved in context
