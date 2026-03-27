## 1. Planner — Milestone Dataclass & Decomposition

- [x] 1.1 Add `Milestone` dataclass to `planner.py` with fields: `goal: str`, `expected_output: str`, `iteration_budget: int`
- [x] 1.2 Write `MILESTONE_PLANNER_SYSTEM` prompt constant (goal-category descriptions, NO tool names listed)
- [x] 1.3 Implement `plan_milestones(command, session, llm, skill_def) -> list[Milestone]` with single LLM call and JSON parsing
- [x] 1.4 Implement fallback: if parse fails or returns 0 milestones, return a single `Milestone` covering the entire command
- [x] 1.5 Apply `settings.cli_max_iterations` as default `iteration_budget` for any milestone missing the field
- [x] 1.6 Add `_parse_milestones(raw: str) -> list[Milestone]` helper (mirrors existing `_parse_plan()` pattern)

## 2. Planner — Milestone-Aware `decide_next_step()`

- [x] 2.1 Add `milestone_goal: str` and `prior_context: str` optional parameters to `decide_next_step()`
- [x] 2.2 Update `DECIDE_NEXT_STEP_SYSTEM` to reference `milestone_goal` when provided (executor focuses on milestone, not full command)
- [x] 2.3 Inject `prior_context` section into the user message when non-empty (labelled "Prior milestone context")
- [x] 2.4 Leave all existing `decide_next_step()` callers unchanged (parameters are optional with defaults)

## 3. Context Compression

- [x] 3.1 Implement `_compress_milestone_result(milestone: Milestone, raw_result: str, llm) -> str` in `shell.py`
- [x] 3.2 Compression prompt: instruct LLM to produce ≤200-token summary preserving paths, IDs, numeric values
- [x] 3.3 Fallback: on LLM exception, return `raw_result[:1000]` truncated at last newline
- [x] 3.4 Log compression outcome at DEBUG level (token count from response metadata if available)

## 4. Shell — Milestone Execute Loop

- [x] 4.1 Rename existing `_dynamic_execute_loop()` to `_legacy_execute_loop()` in `shell.py` (keep as fallback)
- [x] 4.2 Implement `_milestone_execute_loop(command, skill_def, session, cancel_token) -> str`
- [x] 4.3 Call `plan_milestones()` at the start; log milestone list via `renderer.print_info()`
- [x] 4.4 Outer loop: iterate over milestones, pass each to a per-milestone sub-loop method
- [x] 4.5 Implement `_execute_milestone(milestone, prior_context, session, cancel_token) -> str` per-milestone sub-loop
- [x] 4.6 Inside `_execute_milestone`: call `decide_next_step(milestone_goal=milestone.goal, prior_context=prior_context, ...)` each iteration
- [x] 4.7 Wrap tool decision in a transient `PlanStep` and delegate to `SkillExecutor._execute_step()`
- [x] 4.8 Honour `milestone.iteration_budget` as the loop's `max_iterations`
- [x] 4.9 After each milestone completion, call `_compress_milestone_result()` and accumulate in `prior_context`
- [x] 4.10 Replace the call-site in `_run_command()`: call `_milestone_execute_loop()` instead of `_dynamic_execute_loop()`
- [x] 4.11 Wire `SkillExecutor` into `_execute_milestone`: instantiate once per `SkillShell` and reuse

## 5. Per-Step Approval in Milestone Path

- [x] 5.1 Move the write-op per-step approval block from `_dynamic_execute_loop()` into `_execute_milestone()` (before delegating to `SkillExecutor._execute_step()`)
- [x] 5.2 Confirm that skipped steps (user says N) are recorded in `tool_history` with status `"skipped"` and do not advance iteration count

## 6. Audit & Session

- [x] 6.1 Add milestone-level entry to session manifest: `milestone_goal`, `compressed_summary`, `iterations_used`, `status` (done/failed)
- [x] 6.2 Ensure existing `StepRecord` writes inside `_execute_step()` continue to fire (no regression)
- [x] 6.3 Update `log_audit()` calls: replace `dynamic_execute_start/done` with `milestone_execute_start/done` for the new path

## 7. Tests

- [x] 7.1 Unit test `plan_milestones()`: mock LLM returning valid JSON → assert correct `Milestone` list
- [x] 7.2 Unit test `plan_milestones()` fallback: mock LLM returning invalid JSON → assert single fallback milestone
- [x] 7.3 Unit test `_compress_milestone_result()`: mock LLM returning summary → assert truncation fallback on exception
- [x] 7.4 Unit test `decide_next_step()` with `milestone_goal` param: assert goal appears in constructed user message
- [x] 7.5 Integration test `_milestone_execute_loop()` with 2 milestones (mock tools): assert second milestone receives compressed first-milestone context
- [x] 7.6 Regression: run existing `test_router.py` and `test_smart_routing.py` — assert all pass unchanged

## 8. Documentation & Cleanup

- [x] 8.1 Update `planner.py` module docstring to reflect two-layer architecture (Milestone Planner + Step Executor)
- [x] 8.2 Update `shell.py` module docstring; note `_legacy_execute_loop()` is for debug only
- [x] 8.3 Update `executor.py` module docstring: `execute_plan()` is now used in milestone sub-loops (no longer legacy)
- [x] 8.4 Add `# TODO: remove legacy loop after 2-week bake period` comment on `_legacy_execute_loop()`
