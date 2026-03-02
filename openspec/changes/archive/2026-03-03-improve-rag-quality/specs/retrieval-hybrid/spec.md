---
title: Hybrid Retrieval
domain: retrieval
---

## MODIFIED Requirements

### Requirement: Document reading with explicit error reporting
The system SHALL provide a `read_file` tool that returns the full content of a file (or a specific line range) or a detailed error message if the read fails.

#### Scenario: File read success
- **WHEN** `read_file(path)` is called with a valid path within `allowed_paths`
- **THEN** the system SHALL return the UTF-8 text content of the file.

#### Scenario: File read with line range
- **WHEN** `read_file(path, start_line=N, end_line=M)` is called with valid line range
- **THEN** the system SHALL return only lines N through M of the file
- **AND** the result SHALL include a header line indicating `[Lines N-M of {path}]`

#### Scenario: File not found
- **WHEN** `read_file(path)` is called with a path that does not exist but is within `allowed_paths`
- **THEN** the system SHALL return an error message starting with `[ERROR: NOT_FOUND]`.

#### Scenario: Access denied
- **WHEN** `read_file(path)` is called with a path outside `allowed_paths`
- **THEN** the system SHALL return an error message starting with `[ERROR: ACCESS_DENIED]`
- **AND** the message SHALL include the list of currently allowed base directories.

## ADDED Requirements

### Requirement: vector_search explicit no-results feedback
The `vector_search` tool SHALL return a structured "no results" message when no chunks pass the score threshold, instead of an empty JSON array.

#### Scenario: No results above threshold
- **WHEN** `vector_search` is called and all chunks have distance >= threshold (or no chunks exist)
- **THEN** the tool SHALL return `{"status": "no_results", "tool": "vector_search", "message": "No relevant documents found for query: '<query>'. Try different keywords."}`
- **AND** the tool SHALL NOT return `[]`
