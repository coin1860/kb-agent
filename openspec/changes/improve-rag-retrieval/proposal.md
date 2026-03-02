## Why

The current RAG retrieval strategy has poor recall on the first iteration. When `vector_search` is called with a single unmodified user query and the results are deemed irrelevant by the CRAG grader, the system falls back to LLM-based replanning which typically just rephrases the query — producing equally poor results. Real-world testing shows this pattern fails on straightforward Chinese queries like "交易密码几位数？" where the first search returns 5 chunks that get discarded, and the retry with an English translation finds even less.

Two key improvements are needed:
1. **First iteration should cast a wider net** by decomposing the query into multiple sub-queries for parallel vector search
2. **Retry rounds should follow clues** from Round 1 results (file paths, Jira ticket IDs, page references) rather than blindly rephrasing

## What Changes

- **Sub-question decomposition on first iteration**: Instead of sending one `vector_search(original_query)`, use a lightweight LLM call to split the query into 3 sub-queries, then execute 3 parallel `vector_search` calls. Keep existing URL/Jira keyword detection as a fast-path that skips decomposition.
- **Chunk deduplication**: When multiple sub-queries return overlapping chunks, deduplicate by chunk ID before grading.
- **Preserve file hints on RE_RETRIEVE**: Currently, when the grader returns RE_RETRIEVE, all context is discarded. The new behavior preserves file paths, ticket IDs, and other clues from Round 1 for the planner to follow.
- **Enhanced planner prompt for retry rounds**: Update `PLAN_SYSTEM` to strongly guide the LLM toward following clues (read_file, jira_fetch, confluence_fetch) rather than rephrasing searches. The LLM decides which tool to use based on what clues exist.
- **Remove hardcoded Jira regex from plan_node**: Replace the `[A-Z]+-\d+` regex in rule-based routing with LLM-driven intent detection in the decompose step, since Jira keys can have varied prefixes (FSR-123, WCL-123, etc.).

## Capabilities

### New Capabilities
- `retrieval-query-decompose`: LLM-based query decomposition into sub-queries for parallel vector search on the first retrieval round

### Modified Capabilities
- `routing-adaptive`: First-round routing changes from single vector_search to decomposed multi-query; URL/Jira detection moves to pre-decompose guard; Jira detection becomes LLM-driven instead of regex
- `synthesis-corrective-rag`: RE_RETRIEVE action now preserves file hints from discarded context for the next planner round
- `retrieval-context-expand`: REFINE/RE_RETRIEVE follow-up now LLM-driven with prompt guidance toward read_file/jira_fetch/confluence_fetch based on clues

## Impact

- **Files modified**: `src/kb_agent/agent/nodes.py` (plan_node, grade_evidence_node, new _decompose_query), `src/kb_agent/agent/state.py` (new context_file_hints field), `src/kb_agent/agent/tools.py` (no change expected)
- **LLM usage**: +1 lightweight LLM call per query for decomposition (but eliminates most wasted retry rounds)
- **Backward compatible**: No API or config changes; existing tools and graph topology unchanged
- **Tests affected**: `tests/agent/test_e2e_plan_node.py`, `tests/agent/test_grade_evidence.py`
