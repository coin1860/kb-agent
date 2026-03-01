## 1. Update GrepTool Implementation

- [x] 1.1 Remove `_bm25_rerank` method from `GrepTool` in `src/kb_agent/tools/grep_tool.py`.
- [x] 1.2 Update `search()` in `GrepTool` to directly return results without calling `_bm25_rerank`.
- [x] 1.3 Remove `rank_bm25` import and any related BM25 comments.

## 2. Update Hybrid Search Logic

- [x] 2.1 Verify `hybrid_search` tool (likely in `src/kb_agent/agent/tools.py` or similar) correctly assigns rank-based RRF scores to `grep_search` results, ignoring `bm25_score`.
- [x] 2.2 Ensure that RRF fusion logic does not break if a `bm25_score` field is missing from grep results.

## 3. Update Tests

- [x] 3.1 Update `tests/agent/test_hybrid_search.py`: remove assertions on `bm25_score` for grep results.
- [x] 3.2 Update `tests/agent/test_hybrid_search.py`: adjust mock return values for `grep_search` to omit `bm25_score`.
- [x] 3.3 Find and fix any other tests that mock or assert BM25 ranking for grep tools.

## 4. Verification

- [x] 4.1 Run the entire test suite (`pytest`) and ensure all tests pass.
- [x] 4.2 Manually test query "kb-agent 是什么" through the CLI or TUI to confirm the Agent surfaces the exact markdown file correctly instead of returning 0 results.
