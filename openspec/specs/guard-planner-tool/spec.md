---
title: Planner Tool Guard
domain: guard
---

# planner-tool-guard Specification

## Purpose
TBD - created by archiving change fix-rag-planner-routing. Update Purpose after archive.
## Requirements
### Requirement: Filter tool extraction by routing whitelist
The system SHALL only extract tools from LLM fallback text that are present in `routing_plan.suggested_tools`, when a routing plan exists.

#### Scenario: Routing plan suggests vector_search only
- **WHEN** `routing_plan.suggested_tools` is `["vector_search"]`
- **AND** the LLM response mentions `grep_search`, `vector_search`, `jira_fetch`, `confluence_fetch`, `web_fetch` in its reasoning text
- **THEN** `_extract_tools_from_text` extracts ONLY `vector_search`
- **AND** `grep_search`, `jira_fetch`, `confluence_fetch`, `web_fetch` are NOT included

#### Scenario: No routing plan available
- **WHEN** `routing_plan` is None or has no `suggested_tools`
- **THEN** `_extract_tools_from_text` extracts all mentioned tools (current behavior preserved)

### Requirement: Validate tool applicability before invocation
The system SHALL validate that a tool is applicable to the given query before including it in the tool call list.

#### Scenario: Jira tool with no ticket pattern
- **WHEN** the query does not contain a Jira ticket pattern (e.g., `[A-Z]+-\d+`)
- **THEN** `jira_fetch` SHALL NOT be included in tool calls even if mentioned by the LLM

#### Scenario: Jira tool with valid ticket pattern
- **WHEN** the query contains a Jira ticket pattern (e.g., "PROJ-123 的状态是什么？")
- **THEN** `jira_fetch` SHALL be included with `issue_key` set to the extracted ticket ID (e.g., "PROJ-123")

#### Scenario: Web fetch with no URL
- **WHEN** the query does not contain an HTTP/HTTPS URL
- **THEN** `web_fetch` SHALL NOT be included in tool calls

#### Scenario: Web fetch with valid URL
- **WHEN** the query contains a URL (e.g., "总结 https://example.com 的内容")
- **THEN** `web_fetch` SHALL be included with `url` set to the extracted URL

#### Scenario: Confluence with no page reference
- **WHEN** the query does not contain `confluence`, `wiki`, or a numeric page ID
- **THEN** `confluence_fetch` SHALL NOT be included in tool calls

#### Scenario: General search tools are always applicable
- **WHEN** the query is any text
- **THEN** `grep_search`, `vector_search`, `hybrid_search`, `local_file_qa`, `read_file`, `graph_related` are always considered applicable

### Requirement: Build tool-appropriate arguments
The system SHALL construct tool arguments appropriate to each tool's expected parameter type, instead of using the raw query for all tools.

#### Scenario: Search tools use query or sub-question text
- **WHEN** a search tool (`grep_search`, `vector_search`, `hybrid_search`, `local_file_qa`) is invoked
- **THEN** the `query` argument SHALL be the sub-question text (if sub-questions exist) or the original query

#### Scenario: Jira fetch uses extracted issue key
- **WHEN** `jira_fetch` is invoked
- **THEN** the `issue_key` argument SHALL be the extracted ticket ID (e.g., "PROJ-123"), NOT the raw user question

#### Scenario: Web fetch uses extracted URL
- **WHEN** `web_fetch` is invoked
- **THEN** the `url` argument SHALL be the extracted HTTP/HTTPS URL, NOT the raw user question

#### Scenario: Tool arg extraction returns None for invalid input
- **WHEN** a tool's required argument cannot be extracted from the query (e.g., no URL found for web_fetch)
- **THEN** the tool call SHALL be skipped entirely

