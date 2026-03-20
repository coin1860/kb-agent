## 1. State Updates

- [x] 1.1 Update `AgentState` in `src/kb_agent/agent/state.py` to add `discovered_entities`, `task_queue`, `attempted_task_ids`, `reflection_verdict`, and `knowledge_gaps`.

## 2. Core Logic Implementation

- [x] 2.1 Implement `reflect_node` in `src/kb_agent/agent/nodes.py` with zero-LLM Regex extraction logic for Jira IDs and Confluence Page IDs, modifying `AgentState`. includes validation using context bounds for Confluence.
- [x] 2.2 Update `grade_evidence_node` in `src/kb_agent/agent/nodes.py` to remove complex branching output from node (it simply yields internal scores/outcomes; all branching delegates to `reflect_node`).
- [x] 2.3 Modify `plan_node` in `src/kb_agent/agent/nodes.py` to add a fast path (`iteration > 0`) that pulls generated task payloads directly from `task_queue` to `pending_tool_calls` without LLM calls.
- [x] 2.4 Modify `synthesize_node` in `src/kb_agent/agent/nodes.py` to append explicit text highlighting unresolved items from `knowledge_gaps` at the end of the AI response.

## 3. Graph Topology Updates

- [x] 3.1 Update `build_graph` in `src/kb_agent/agent/graph.py` to add `reflect_node`.
- [x] 3.2 Add conditional edge after `reflect_node` parsing `reflection_verdict` to route to either `plan` (precision) or `synthesize` (completed/stuck).
- [x] 3.3 Ensure edge runs unconditionally from `grade_evidence_node` direct to `reflect_node`.

## 4. Tests and Verification

- [x] 4.1 Create `tests/test_reflect_node.py` to ensure `reflect_node` correctly extracts Jira and Confluence IDs with exact Regex tests, including checking the false-positive bounding rules.
- [x] 4.2 Create/Update `tests/test_plan_node.py` to assert the LLM is short-circuited when reading pending discrete requests from `task_queue` natively.
- [x] 4.3 Update `tests/test_graph.py` to verify the modified routing logic (`grade_evidence_node` -> `reflect_node` -> `plan_node` / `synthesize_node`) is correctly evaluated in all three potential verdicts (`sufficient`, `needs_precision`, and `exhausted`).
