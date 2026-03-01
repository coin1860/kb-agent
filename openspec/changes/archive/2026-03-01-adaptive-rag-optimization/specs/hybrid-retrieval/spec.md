## ADDED Requirements

### Requirement: Context window enrichment for grep results
The system SHALL return surrounding context (±10 lines) for each grep match instead of single matched lines.

#### Scenario: Grep match with context window
- **WHEN** `grep_search` finds a match at line N in a file
- **THEN** the result SHALL include lines max(1, N-10) through N+10 as a single passage
- **AND** the matched line is highlighted or marked within the passage

#### Scenario: Multiple matches in same file within context range
- **WHEN** two matches in the same file are within 20 lines of each other
- **THEN** the system SHALL merge them into a single passage to avoid duplication

### Requirement: BM25 scoring and ranking of grep results
The system SHALL apply BM25 scoring to rank grep results by relevance to the query, filtering out low-scoring noise.

#### Scenario: BM25 ranking applied to grep output
- **WHEN** `grep_search` returns N raw matches
- **THEN** the system computes a BM25 score for each match passage against the query
- **AND** results are sorted by BM25 score descending
- **AND** only the top 10 results are returned

#### Scenario: Low-relevance grep results filtered
- **WHEN** a grep match passage has a BM25 score below the 25th percentile of all match scores
- **THEN** the result is excluded from the returned set

### Requirement: Hybrid search combining BM25 and vector retrieval
The system SHALL provide a `hybrid_search` tool that combines BM25-scored grep results with vector search results using Reciprocal Rank Fusion (RRF).

#### Scenario: Hybrid search fusion
- **WHEN** `hybrid_search(query)` is called
- **THEN** the system executes both `grep_search` (with BM25) and `vector_search` in parallel
- **AND** the system computes RRF scores using `RRF_score(d) = Σ 1/(k + rank_i(d))` with k=60
- **AND** the system returns the top 10 results ranked by fused RRF score

#### Scenario: One source returns empty
- **WHEN** `grep_search` returns 0 results but `vector_search` returns results (or vice versa)
- **THEN** the system returns results from the non-empty source ranked by their original scores
- **AND** the system does NOT fail or return empty
