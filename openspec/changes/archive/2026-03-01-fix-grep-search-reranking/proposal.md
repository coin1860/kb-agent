## Why

The current `grep_search` tool uses BM25 algorithm to rerank and filter its results before returning them to the agent. However, because `grep_search` only returns a very small corpus of documents that *already* contain the exact search term, the BM25 Document Frequency (DF) approaches the corpus size, causing Inverse Document Frequency (IDF) scores to become negative. Combined with a strict threshold (score >= 1.0), this filters out perfectly valid exact matches, causing queries for specific application terms (like "kb-agent") to return 0 results. This change removes the BM25 reranking from `grep_search` entirely, allowing the raw exact matches to be surfaced to the RAG system.

## What Changes

- Remove BM25 reranking logic from `GrepTool.search()` in `src/kb_agent/tools/grep_tool.py`.
- **BREAKING**: `grep_search` will no longer return a `bm25_score` field in its output dictionary.
- Update tests that rely on the BM25 reranking behavior.
- Update the `hybrid-retrieval` specification to reflect that `grep_search` results are not reranked.

## Capabilities

### New Capabilities
None

### Modified Capabilities
- `hybrid-retrieval`: Remove the specification that `grep_search` results are reranked using BM25, and remove the `bm25_score` property from its output contract.

## Impact

- **Affected Code**: `src/kb_agent/tools/grep_tool.py`, `tests/agent/test_hybrid_search.py` (and potentially other tests mocking `grep_search`).
- **Systems**: Core Agent RAG retrieval capability will get more results for exact keyword searches, avoiding false-negative "I don't know" answers.
