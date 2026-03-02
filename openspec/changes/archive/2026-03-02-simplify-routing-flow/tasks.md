## 1. Clean Up Legacy Routing

- [x] 1.1 Remove `analyze_and_route_node` function and its associated prompt (`ANALYZE_SYSTEM`) from `src/kb_agent/agent/nodes.py`.
- [x] 1.2 Update `AgentState` in `src/kb_agent/agent/state.py` to remove `sub_questions`, `routing_plan`, and `query_type` fields.
- [x] 1.3 Update graph topology in `src/kb_agent/agent/graph.py` to set the entry point directly to `plan_node` (or a simplified gateway if required) and remove conditional edges related to `analyze_and_route`.

## 2. Refactor Planning and Tools

- [x] 2.1 Update `PLAN_SYSTEM` prompt in `src/kb_agent/agent/nodes.py` to instruct the LLM to issue parallel calls to `grep_search` and `vector_search` for complex queries instead of relying on hybrid search. Provide clear examples of this parallel tool usage.
- [x] 2.2 Remove dictionary parsing logic (`_build_tool_args` handling `semantic_intent` / `search_keywords`) from `plan_node` in `src/kb_agent/agent/nodes.py` since the state no longer contains these complex nested structures.
- [x] 2.3 Remove or deprecate the `hybrid_search` function definition in `src/kb_agent/agent/tools.py`.
- [x] 2.4 Remove `hybrid_search` from `ALL_TOOLS` list and `TOOL_DESCRIPTIONS` string.

## 3. Verify and Adjust Downstream Nodes

- [x] 3.1 Verify `tool_node` in `src/kb_agent/agent/nodes.py` correctly handles executing multiple tool calls concurrently (it currently iterates through `pending`, which is sufficient, but ensure results from both tools are appended to `context` cleanly).
- [x] 3.2 Ensure `grade_evidence_node` string casting/formatting correctly handles potentially longer lists of context items originating from parallel tool execution. (Adjust token limits/truncation if necessary).

## 4. Testing & Validation

- [x] 4.1 Run standard CLI/TUI tests with simple queries (e.g., exact ticket IDs) to ensure `grep_search` is called alone and works.
- [x] 4.2 Run tests with complex queries to ensure the planner successfully emits parallel tool calls (`grep_search` + `vector_search`) and that both execute successfully.
- [x] 4.3 Verify the system no longer crashes due to JSON parsing failures during the analysis phase.
