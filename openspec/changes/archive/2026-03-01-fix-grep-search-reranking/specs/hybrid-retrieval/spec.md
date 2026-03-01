## REMOVED Requirements

### Requirement: BM25 scoring and ranking of grep results
**Reason**: BM25 IDF calculation produces negative scores when applied to a pre-filtered corpus (where every document contains the term), causing valid exact matches to be dropped.
**Migration**: `grep_search` will now return all exact context window matches without BM25 reranking. Downstream grading relies on the LLM grader.

## MODIFIED Requirements

### Requirement: Hybrid search combining BM25 and vector retrieval
The system SHALL provide a `hybrid_search` tool that combines raw `grep_search` results with vector search results using Reciprocal Rank Fusion (RRF).

#### Scenario: Hybrid search fusion
- **WHEN** `hybrid_search(query)` is called
- **THEN** the system executes both `grep_search` and `vector_search` in parallel
- **AND** the system computes RRF scores using `RRF_score(d) = Σ 1/(k + rank_i(d))` with k=60
- **AND** the system returns the top 10 results ranked by fused RRF score

#### Scenario: One source returns empty
- **WHEN** `grep_search` returns 0 results but `vector_search` returns results (or vice versa)
- **THEN** the system returns results from the non-empty source ranked by their original scores or order
- **AND** the system does NOT fail or return empty
