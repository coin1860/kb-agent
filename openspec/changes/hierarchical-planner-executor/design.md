## Context

The kb-cli agent currently uses a flat, single-level ReAct loop housed in `shell.py:_dynamic_execute_loop()`. In each iteration, `planner.decide_next_step()` asks the LLM to select one tool or emit `final_answer`, appending all raw tool outputs to a growing history that is fed back verbatim. This creates three compounding problems:

1. **Context bloat**: all raw tool outputs accumulate in a single prompt, consuming tokens and degrading model attention on longer tasks.
2. **Cognitive overload on the LLM**: the same model call must simultaneously think strategically ("what phase of the task am I in?") and tactically ("which exact tool, with which exact args?").
3. **Bypassed resilience machinery**: `executor.py:SkillExecutor` already implements Reflect, retry, and Python auto-fix — but `_dynamic_execute_loop()` never calls it, silently losing all that robustness.

## Goals / Non-Goals

**Goals:**
- Introduce a dedicated `plan_milestones()` function that decomposes a goal into 2–5 coarse, verifiable milestones before execution begins.
- Implement `_milestone_execute_loop()` in `shell.py` that runs one Executor sub-loop per milestone.
- Wire the existing `SkillExecutor._execute_step()` (with its Reflect + retry + auto-fix) as the per-step engine inside each milestone sub-loop.
- Introduce cross-milestone context compression so subsequent milestones receive a concise summary rather than raw tool outputs.
- Keep the chitchat and skill-matched execution paths completely unchanged.

**Non-Goals:**
- Full LangGraph state machine refactor (the two-layer loop is implemented imperatively, not as a graph).
- Streaming output per-token during execution.
- Multi-agent parallelism (milestones execute sequentially).
- Changing the approval gate or interrupt/replan UX.

## Decisions

### D1: Milestone as a structured dataclass, not a raw string

**Decision**: Introduce `@dataclass Milestone(goal: str, expected_output: str, iteration_budget: int)` in `planner.py`.

**Why**: A structured milestone gives the Executor a clear "done" signal (`expected_output`) and a resource cap independent of other milestones. Passing raw strings would require the Executor prompt to re-interpret the goal's scope on every step.

**Alternative considered**: Reuse `PlanStep` with a `milestone=True` flag. Rejected — `PlanStep` is tool-centric (`tool`, `args`) whereas a `Milestone` is goal-centric; merging the concepts pollutes both.

---

### D2: Planner prompt does NOT describe individual tools

**Decision**: `MILESTONE_PLANNER_SYSTEM` describes goal types and expected outputs but lists no tool names. The Executor retains full `SKILL_TOOLS_DESCRIPTION`.

**Why**: If the Planner knows about tools it tends to micro-manage them (e.g., "Step 2: call vector_search"). Hiding tools forces the Planner to think in outcomes ("retrieve relevant knowledge"), which is the correct level of abstraction.

**Alternative considered**: Include a short tool capability summary (not arg-level detail). Rejected — any tool mention in the Planner prompt leaked tactical thinking in early testing analogues across similar architectures.

---

### D3: Context compression after each milestone via existing `_summarise_python_result()` pattern

**Decision**: After each milestone's sub-loop emits a result, call `_compress_milestone_result(milestone, raw_result, llm)` — a new 1-shot LLM call capped to 200 tokens — and forward only the compressed summary to the next milestone's context.

**Why**: Raw tool outputs can be multi-kilobyte JSON blobs. Compressing each milestone's output to a paragraph keeps the per-milestone prompt size stable regardless of task length.

**Alternative considered**: Pass last N characters of raw output. Rejected — truncating structured data (JSON, tables) mid-line produces garbage context. Semantic compression is more reliable.

---

### D4: Reuse `SkillExecutor._execute_step()` with a synthesized `PlanStep`

**Decision**: Inside each milestone sub-loop, the Executor calls `decide_next_step()` to get `{tool, args}`, wraps them in a transient `PlanStep`, and delegates to `SkillExecutor._execute_step()`.

**Why**: `_execute_step()` already provides Reflect (continue/retry/abort), `_MAX_RETRIES`, and `_auto_fix_python()`. Replicating this in `_milestone_execute_loop()` would be duplication; delegating eliminates the maintenance divergence that currently exists between `execute_plan()` and `_dynamic_execute_loop()`.

**Alternative considered**: Refactor `_dynamic_execute_loop()` in place to add Reflect. Rejected — the two-layer architecture is a better separation of concerns; adding Reflect to the flat loop does not solve the context bloat or cognitive overload problems.

---

### D5: `cli_max_iterations` becomes the per-milestone default budget

**Decision**: `settings.cli_max_iterations` (default 3) is used as the default `iteration_budget` for each milestone. The Planner may override per milestone (e.g., budget=1 for a simple fetch, budget=5 for code generation).

**Why**: Backward compatible — existing deployments with `cli_max_iterations=3` keep equivalent per-milestone behavior. Users can tune without a new config key.

**Alternative considered**: New `cli_milestone_budget` config key. Deferred — can be added later if users need independent control; premature to add now.

## Risks / Trade-offs

| Risk | Mitigation |
|------|-----------|
| Milestone Planner over-decomposes simple queries (e.g., "hi" → 3 milestones) | `plan_milestones()` falls back to a single milestone covering the whole command if LLM returns 0 or 1 milestones; chitchat is already short-circuited before milestone planning |
| LLM within milestone declares `final_answer` prematurely, skipping remaining milestones | Executor sub-loop's `final_answer` only terminates the *current* milestone, not the whole task; the outer loop continues to subsequent milestones |
| Two LLM calls before first tool (Planner + first Executor decide) increases latency for simple tasks | For single milestone tasks, the overhead is one extra LLM call; acceptable trade-off. Chitchat avoids this entirely |
| Context compression loses critical information (e.g., a specific file path produced by milestone 1) | Compression prompt explicitly instructs the LLM to preserve structured artefacts (paths, IDs, keys); raw result is also stored in `session` for audit |
| `_execute_step()` retry loop combined with outer milestone retry creates exponential retry storms | Milestone-level re-decomposition is opt-in (only if abort verdict fires); default is forward-only across milestones |

## Migration Plan

1. All changes are additive: `plan_milestones()` is a new function; existing `generate_plan()` and `decide_next_step()` are preserved.
2. `_dynamic_execute_loop()` in `shell.py` is renamed `_legacy_execute_loop()` and a new `_milestone_execute_loop()` replaces it at the call site. A `--legacy-loop` CLI flag can toggle back for debugging.
3. No config schema changes required for the initial rollout.
4. Rollback: revert the call site in `_run_command()` from `_milestone_execute_loop()` to `_legacy_execute_loop()`.

## Open Questions

- **Q1**: Should the Planner be allowed to specify a `skill_hint` per milestone (suggesting which skill playbook step maps to it)? Could improve skill-matched task quality but adds coupling between Planner and Skill loader.
- **Q2**: If milestone N aborts (unrecoverable error), should the Planner re-decompose the remaining milestones or halt? Current design halts; re-decomposition is more resilient but requires another architecture layer.
- **Q3**: Long-term: does the milestone concept map cleanly onto a LangGraph sub-graph, enabling parallel milestone execution? Deferred to future exploration.
