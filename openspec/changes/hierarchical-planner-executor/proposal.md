## Why

The current agent execution model is a flat, single-level ReAct loop: `decide_next_step()` asks the LLM to pick one tool at a time until reaching `final_answer`. This works for simple 1–3 step tasks but breaks down on complex, multi-stage goals — the LLM simultaneously handles both strategic decomposition and tactical tool selection in a single prompt, causing poor planning quality, context window bloat (entire tool history in every call), and a 3-iteration cap that is too coarse-grained for longer workflows.

## What Changes

- **Introduce a high-level Milestone Planner**: a new `plan_milestones()` function in `planner.py` that decomposes a user command into an ordered list of coarse-grained, verifiable milestones (e.g., "fetch data", "analyze and generate script", "write report"). This is a single upfront LLM call focused only on *what* goals to achieve, not *how*.
- **Refactor `_dynamic_execute_loop()` in `shell.py`** to iterate over milestones rather than raw tool calls; each milestone is handed to an executor loop.
- **Promote `SkillExecutor` back into the main execution path**: the existing `execute_plan()` logic already has Think→Act→Observe→Reflect with retry and auto-fix — wire it as the per-milestone executor instead of the simplified loop in `shell.py`.
- **Add cross-milestone context compression**: after each milestone completes, summarise its result (similar to the existing `_summarise_python_result()`) so subsequent milestone prompts stay concise.
- **Decouple Planner LLM prompt from tool details**: the Planner should reason about goals only; tool-level instructions belong exclusively in the Executor prompt.
- **Per-milestone iteration budget**: each milestone gets its own `max_iterations` instead of a single global cap, enabling trivial milestones to complete in 1 step and complex ones in 5+.

## Capabilities

### New Capabilities

- `milestone-planner`: High-level goal decomposition into an ordered milestone list. Produces structured `Milestone` objects (goal description, expected output type, iteration budget). Replaces the dual-role `decide_next_step()` planner prompt with a dedicated milestone-decomposition prompt.
- `milestone-executor`: Per-milestone Think→Act→Observe loop that operates with a focused context (milestone goal + milestone-local tool history + compressed summaries of prior milestones). Reuses `SkillExecutor._execute_step()` internals.
- `context-compression`: After each milestone completes, an LLM call compresses the raw tool outputs into a one-paragraph summary that is forwarded to subsequent milestone context.

### Modified Capabilities

- `routing-engine`: The `free_agent` branch now enters the two-layer loop instead of the flat `decide_next_step()` loop. Skill-matched branches are unchanged.
- `reflection-replanning`: Reflection (continue/retry/abort) now operates at the milestone level as well as the step level — a milestone that repeatedly aborts can trigger a Planner re-decomposition.
- `tool-error-handling`: Auto-fix for `run_python` and retry logic are now consistently used in the primary execution path (not only in the static `execute_plan()` path that was previously bypassed).

## Impact

- **Modified files**: `src/kb_agent/skill/planner.py`, `src/kb_agent/skill/shell.py`, `src/kb_agent/skill/executor.py`
- **New dataclasses**: `Milestone` in `planner.py`
- **Backward compatible**: skill-matched execution and chitchat paths are untouched; config `cli_max_iterations` is repurposed as per-milestone budget default
- **No new dependencies**: uses existing LangChain, Rich, and internal tool infrastructure
- **Tests**: existing unit tests for `decide_next_step`, `generate_plan`, `router` remain valid; new tests needed for `plan_milestones()` and the two-layer loop
