## MODIFIED Requirements

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
