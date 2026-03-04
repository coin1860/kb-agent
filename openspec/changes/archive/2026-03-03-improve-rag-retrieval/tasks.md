## 1. State Schema Update

- [x] 1.1 Add `context_file_hints: list[str]` field to `AgentState` in `state.py`

## 2. Query Decomposition

- [x] 2.1 Add `DECOMPOSE_SYSTEM` prompt constant in `nodes.py` — instructs LLM to output JSON with `{"action": "decompose", "sub_queries": [...]}` or `{"action": "direct", "tool": "...", "args": {...}}`
- [x] 2.2 Implement `_decompose_query(query: str, state: AgentState)` function in `nodes.py` — calls LLM, parses JSON response, returns list of tool calls
- [x] 2.3 Update `plan_node` Round 1 routing: replace regex-based Jira detection with `_decompose_query()`, keep URL regex guard before LLM call

## 3. Chunk Deduplication

- [x] 3.1 Add chunk deduplication logic in `tool_node` — when processing multiple vector_search results in one round, deduplicate by chunk ID keeping highest score

## 4. Context Hint Preservation

- [x] 4.1 Update `grade_evidence_node` to extract file paths, Jira ticket IDs, and page references from all context items (even discarded ones) and store in `context_file_hints`
- [x] 4.2 Remove hardcoded REFINE read_file rule from `plan_node` (lines 370-377) — let LLM planner handle all retry decisions

## 5. Enhanced Retry Prompt

- [x] 5.1 Update `PLAN_SYSTEM` prompt to include retry guidance: present `context_file_hints` as structured clue data, instruct planner to prioritize read_file/jira_fetch/confluence_fetch over rephrased vector_search

## 6. Testing

- [x] 6.1 Update `test_e2e_plan_node.py` — adjust `test_plan_node_e2e_conceptual_chinese` for new decompose behavior (Round 1 now uses LLM decompose, not direct vector_search)
- [x] 6.2 Update `test_e2e_plan_node.py` — adjust `test_plan_node_e2e_jira_ticket` for LLM-based Jira detection (no longer regex-matched on iteration 0)
- [x] 6.3 Add test for `_decompose_query()` — verify decompose returns 3 sub-queries for general questions, and direct tool call for Jira-style queries
- [x] 6.4 Add test for chunk deduplication — verify duplicate chunk IDs are merged keeping highest score
- [x] 6.5 Run full test suite: `python -m pytest tests/agent/ -v`
