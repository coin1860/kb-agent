---
title: Hybrid Retrieval
domain: retrieval
---

# hybrid-retrieval Specification

## Purpose
Hybrid retrieval system combining exact keyword-based passage search and semantic vector search.
## Requirements
### Requirement: Context window enrichment for grep results
The system SHALL return surrounding context (±10 lines) for each grep match instead of single matched lines.

#### Scenario: Grep match with context window
- **WHEN** `grep_search` finds a match at line N in a file
- **THEN** the result SHALL include lines max(1, N-10) through N+10 as a single passage
- **AND** the matched line is highlighted or marked within the passage

#### Scenario: Multiple matches in same file within context range
- **WHEN** two matches in the same file are within 20 lines of each other
- **THEN** the system SHALL merge them into a single passage to avoid duplication

### Requirement: Hybrid search combining exact keyword and vector retrieval
The system SHALL provide a `hybrid_search` tool that combines raw `grep_search` results with `vector_search` results using Reciprocal Rank Fusion (RRF). To maximize the effectiveness of both underlying engines, the tool SHALL accept separate arguments tailored for semantic meaning and exact keyword matching.

#### Scenario: Hybrid search fusion with separate arguments
- **WHEN** `hybrid_search(semantic_query, exact_keywords)` is called
- **THEN** the system executes `grep_search(query=exact_keywords)` and `vector_search(query=semantic_query)` in parallel
- **AND** the system computes RRF scores using `RRF_score(d) = Σ 1/(k + rank_i(d))` with k=60
- **AND** the system returns the top 10 results ranked by fused RRF score

#### Scenario: One source returns empty
- **WHEN** `grep_search` returns 0 results but `vector_search` returns results (or vice versa)
- **THEN** the system returns results from the non-empty source ranked by their original scores or order
- **AND** the system does NOT fail or return empty

#### Scenario: Argument fallback
- **WHEN** `exact_keywords` is missing, empty, or identical to `semantic_query`
- **THEN** the system SHALL attempt to extract nouns or terms internally before calling `grep_search` OR proceed gracefully using whatever keywords were provided

### Requirement: Vector Search Threshold
The system SHALL discard retrieved vector chunks whose distance metric exceeds the configured `vector_score_threshold`. Default threshold MUST be 0.5.

#### Scenario: Vector search with results below threshold
- **WHEN** the `VectorTool.search` is executed and retrieves chunks with `distances[i]` < `vector_score_threshold` (for L2)
- **THEN** the chunks are included in the returned list

#### Scenario: Vector search with results above threshold
- **WHEN** the `VectorTool.search` is executed and retrieves chunks with `distances[i]` >= `vector_score_threshold`
- **THEN** the chunks are discarded and NOT included in the returned list

### Requirement: Document reading with explicit error reporting
The system SHALL provide a `read_file` tool that returns the full content of a file or a detailed error message if the read fails.

#### Scenario: File read success
- **WHEN** `read_file(path)` is called with a valid path within `allowed_paths`
- **THEN** the system SHALL return the UTF-8 text content of the file.

#### Scenario: File not found
- **WHEN** `read_file(path)` is called with a path that does not exist but is within `allowed_paths`
- **THEN** the system SHALL return an error message starting with `[ERROR: NOT_FOUND]`.

#### Scenario: Access denied
- **WHEN** `read_file(path)` is called with a path outside `allowed_paths`
- **THEN** the system SHALL return an error message starting with `[ERROR: ACCESS_DENIED]`
- **AND** the message SHALL include the list of currently allowed base directories.

### Requirement: Search feedback and citations
The system SHALL provide informative feedback during search execution and accurate citations in synthesized answers.

#### Scenario: Enhanced search log feedback
- **WHEN** a search tool (`grep_search`, `vector_search`, `hybrid_search`) returns a list of results
- **THEN** the system SHALL emit a status message to the TUI including the character count
- **AND** the message SHALL include the number of unique files matched (for grep) or total chunks found (for vector/hybrid).

#### Scenario: Accurate file citations
- **WHEN** the system formats tool results for the LLM or user display
- **THEN** it SHALL prioritize using the actual file path from metadata (e.g., `path` or `file_path`) over generic source identifiers like "local_file".

