---
title: Retrieval Context Expansion
domain: retrieval
---

## ADDED Requirements

### Requirement: Line-range read_file support
The `read_file` tool SHALL accept optional `start_line` and `end_line` integer parameters to read a specific line range from a file instead of the full content.

#### Scenario: Read specific line range
- **WHEN** `read_file(file_path, start_line=50, end_line=250)` is called
- **THEN** the system SHALL return only lines 50 through 250 (inclusive) of the file
- **AND** the result SHALL include a header indicating the line range: `[Lines 50-250 of {file_path}]`

#### Scenario: Read without line range (backward compatible)
- **WHEN** `read_file(file_path)` is called without `start_line` or `end_line`
- **THEN** the system SHALL return the full file content (existing behavior)
- **AND** the 8000-character truncation limit SHALL still apply

#### Scenario: Line range clamping
- **WHEN** `start_line` is less than 1 or `end_line` exceeds the file's total lines
- **THEN** the system SHALL clamp the range to valid bounds without raising an error

### Requirement: Automatic context expansion on REFINE
When the grader returns REFINE action, `plan_node` SHALL automatically extract file paths from previous vector_search results and issue `read_file` calls to fetch surrounding context, before falling back to LLM-planned retry.

#### Scenario: REFINE triggers file read follow-up
- **WHEN** `grader_action` is `REFINE` and previous tool_history contains `vector_search` results with file paths
- **THEN** `plan_node` SHALL extract unique file paths from context items
- **AND** `plan_node` SHALL issue `read_file` calls for up to 3 files not already in `files_read`
- **AND** the LLM planner SHALL NOT be invoked for this round

#### Scenario: REFINE with no new files to read
- **WHEN** `grader_action` is `REFINE` but all discovered file paths are already in `files_read`
- **THEN** `plan_node` SHALL fall through to the normal LLM planner for retry strategy
