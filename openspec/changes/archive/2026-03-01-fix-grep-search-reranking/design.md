## Context

The `kb-agent` uses `grep_search` to find exact keyword matches across markdown files. Currently, the `GrepTool.search()` applies BM25 algorithm to score these matches and strictly filters out any results with a score below 1.0. Because `grep_search` only returns files that definitely contain the keyword, the corpus length equals the document frequency (DF). This breaks the BM25 IDF formula, producing negative scores for all matches. As a result, exact keyword searches for application-specific terminology (like "kb-agent") are being heavily filtered (often returning 0 results), preventing the RAG system from synthesizing a correct answer.

## Goals / Non-Goals

**Goals:**
- Ensure exact matches found by `grep_search` are passed to the agent without artificial suppression.
- Simplify `grep_search` by removing the defective BM25 reranking logic.
- Ensure `hybrid_search` continues to work (combining un-ranked `grep_search` and scored `vector_search`).

**Non-Goals:**
- Improving or altering the BM25 logic to work on small corpora.
- Altering how `vector_search` ranks its results.
- Removing `rank-bm25` entirely from the project (it may be used elsewhere or in future).

## Decisions

1. **Remove BM25 completely from `GrepTool`**
   - *Rationale*: For exact keyword searches ("find X"), existence is the primary signal of relevance. Sorting by BM25 adds unnecessary complexity and bugs when DF is close to Corpus Size.
   - *Alternatives considered*: Lowering the BM25 threshold to `-infinity`. This would work mechanically, but leaves dead ranking code that provides meaningless negative scores. Removing it clarifies the intent of the tool.

2. **Remove `bm25_score` from `grep_search` return dictionaries**
   - *Rationale*: It is no longer calculated. Any callers expecting this field will need to be adjusted (primarily tests).

3. **Hybrid Search RRF Fusion Update**
   - *Rationale*: `hybrid_search` uses Reciprocal Rank Fusion (RRF). RRF requires a sorted list, but does not strictly require absolute score numbers—it only cares about the *rank* (index) of the item. Since `grep_search` will now return raw results (usually ordered by file/line), we can simply assign them a rank based on their returned order.

## Risks / Trade-offs

- **[Risk] Reduced precision in grep results** → Over-returning results when a common term is searched.
  - *Mitigation*: The LLM `grade_evidence_node` (CRAG) already handles filtering of irrelevant context. We lean on the LLM grader rather than a flawed heuristic filter.
- **[Risk] Test breakage** → Tests asserting BM25 scores or exact result counts from `grep_search` will fail.
  - *Mitigation*: Update all affected tests (like `test_hybrid_search.py`) to remove assertions on `bm25_score` and expect slightly differently ordered raw results.
