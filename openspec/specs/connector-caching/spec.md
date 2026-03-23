# Capability: Connector Caching

## Purpose
Provides file-backed payload caching for remote KB entities (Jira/Confluence) with structured cache-miss fallback and manual invalidation logic.

## Requirements

### Requirement: Persistent JSON API Caching
The system MUST permanently cache single-entity Jira and Confluence lookups locally as JSON payload files.

#### Scenario: Caching consecutive fetches
- **WHEN** the user fetches Confluence page 12345 twice
- **THEN** the first fetch pulls from the Atlassian API and writes to `cache/confluence/12345/main.json`, and the second fetch loads directly from `main.json` without network calls.

### Requirement: Jira Subtask Summary Extraction
When a Jira ticket is fetched and cached, any subtask objects included in the parent API response MUST be extracted and saved locally inside the parent's cache folder.

#### Scenario: Parent with subtasks
- **WHEN** the system fetches FSR-100 and its response contains subtasks FSR-101 and FSR-102
- **THEN** the system MUST save `cache/jira/FSR-100/FSR-101.json` and `cache/jira/FSR-100/FSR-102.json` alongside `main.json`.

### Requirement: Manual Cache Refresh
Users SHALL be able to explicitly bypass the local cache and pull fresh data by using configured keywords like `refresh cache` or `刷新缓存`.

#### Scenario: Chat mode force refresh
- **WHEN** the user types `/jira FSR-123 please refresh cache`
- **THEN** the system ignores the local cache, fetches fresh data via API, overwrites the local JSON files, and processes the response.

#### Scenario: RAG mode force refresh
- **WHEN** the user is in RAG mode and asks "refresh the cache and check Confluence 12345"
- **THEN** the LLM invokes the `confluence_fetch` tool with the `force_refresh=True` parameter, bypassing the local cache.
