## 1. Configuration & State

- [x] 1.1 Add `KB_AGENT_VECTOR_SCORE_THRESHOLD` (default `0.8`) and `KB_AGENT_AUTO_APPROVE_MAX_ITEMS` (default `2`) to `config.py` settings model
- [x] 1.2 Add the two new env vars to `.env.example` with comments

## 2. Analyze & Route — Complexity Classification

- [x] 2.1 Update `ANALYZE_SYSTEM` prompt in `agent/nodes.py` to include `complexity` field (`simple`/`complex`/`chitchat`) and `chitchat` query_type in the output schema
- [x] 2.2 Update `analyze_and_route_node` to parse and store `complexity` in `routing_plan`
- [x] 2.3 Add `log_audit("fast_path_hit", ...)` when chitchat is detected at the routing level

## 3. Graph Topology — Conditional Edges

- [x] 3.1 Add `_route_after_analyze(state)` conditional function in `agent/graph.py` — routes chitchat → synthesize, else → plan
- [x] 3.2 Replace hard edge `analyze_and_route → plan` with `add_conditional_edges("analyze_and_route", _route_after_analyze)`
- [x] 3.3 Add `_route_after_tool_exec(state)` conditional function — routes simple → synthesize, else → grade_evidence
- [x] 3.4 Replace hard edge `tool_exec → grade_evidence` with `add_conditional_edges("tool_exec", _route_after_tool_exec)`
- [x] 3.5 Update graph docstring to reflect new topology

## 4. Grade Evidence — Rule-based Pre-filter

- [x] 4.1 Add rule: read_file results auto-approve (all tool_history entries are `read_file`) with `log_audit("fast_path_hit", {"rule_name": "read_file", ...})`
- [x] 4.2 Add rule: few context items auto-approve (`len(context_items) <= KB_AGENT_AUTO_APPROVE_MAX_ITEMS`) with `log_audit("fast_path_hit", {"rule_name": "few_context", ...})`
- [x] 4.3 Add rule: high vector score auto-approve (all vector_search scores ≥ `KB_AGENT_VECTOR_SCORE_THRESHOLD` from tool_history) with `log_audit("fast_path_hit", {"rule_name": "high_vector_score", ...})`
- [x] 4.4 Refactor existing `local_file_qa` auto-approve to use the same `log_audit("fast_path_hit", ...)` pattern

## 5. Synthesize — Chitchat Mode

- [x] 5.1 Add chitchat detection in `synthesize_node`: when `routing_plan.complexity == "chitchat"`, use a conversational system prompt instead of the "only from evidence" prompt
- [x] 5.2 Skip citation footer when in chitchat mode

## 6. Testing & Verification

- [x] 6.1 Run existing test suite to ensure no regressions
- [x] 6.2 Manual test: chitchat query ("你好") — verify only 2 LLM calls in audit log
- [x] 6.3 Manual test: simple query ("VectorTool 是什么") — verify grade_evidence skipped in audit log
- [x] 6.4 Manual test: complex query ("比较索引管线和查询引擎") — verify full pipeline in audit log
- [x] 6.5 Manual test: read_file scenario — verify rule auto-approve in audit log
- [x] 6.6 Verify `fast_path_hit` events in audit log with correct `path_type` and `rule_name`
