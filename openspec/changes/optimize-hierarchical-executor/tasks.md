## 1. Selective Reflection Optimization

- [x] 1.1 Define a `SAFE_READ_TOOLS` list in `src/kb_agent/skill/executor.py` (e.g. `jira_fetch`, `vector_search`, `get_knowledge`, `ls`, `grep`)
- [x] 1.2 Update `_execute_step` in `src/kb_agent/skill/executor.py` to skip `_reflect` call if tool is safe, output length > 50, and `_is_error_result` is False
- [x] 1.3 Add audit logging to track when reflection is skipped/forced

## 2. Adaptive Context & Long Compression

- [x] 2.1 Update `_milestone_execute_loop` in `src/kb_agent/skill/shell.py` to check `len(raw_result)` before calling `_compress_milestone_result`
- [x] 2.2 Implement 8000 character threshold logic (approx 2k tokens) to bypass compression
- [x] 2.3 Update `_COMPRESS_SYSTEM` prompt in `shell.py` to increase summary limit to 4,000 tokens for cases where compression is still required

## 3. Structural Call Compression (Unified Planning & Resolution)

- [x] 3.1 Update `plan_milestones` (or create returning unified dict) in `src/kb_agent/skill/planner.py` to also return `route` and `summary` alongside milestones to replace `route_intent` and `preview_intent`
- [x] 3.2 Update `_run_command` in `src/kb_agent/skill/shell.py` to use the unified planner instead of 3 separate calls
- [x] 3.3 Remove `_resolve_args` call from `_execute_step` in `src/kb_agent/skill/executor.py`, passing `prior_context/step_outputs` directly into the `decide_next_step` prompt so tools are resolved natively

## 4. Implicit Milestone Termination

- [x] 4.1 Update `decide_next_step` system prompt to recognize "Milestone Accomplished" intent in the same response as a move
- [x] 4.2 Update `_execute_milestone` in `src/kb_agent/skill/shell.py` to parse an optional `status` or `finish` flag from the action JSON to terminate early
- [x] 4.3 Ensure final answer result is correctly captured when early termination occurs

## 5. Verification & Benchmarking

- [x] 5.1 Update `tests/skill/test_milestone_planner.py` with new threshold and skipping logic tests
- [x] 5.2 Benchmark a 2-milestone task (e.g., fetch and summarized report) to verify calling count reduction
- [x] 5.3 Regression run of all skill/shell tests
