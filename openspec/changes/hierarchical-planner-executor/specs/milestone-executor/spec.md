## ADDED Requirements

### Requirement: Execute each milestone via a focused Think-Act-Observe sub-loop
The system SHALL implement `_milestone_execute_loop()` in `shell.py` that iterates over the `Milestone` list from `plan_milestones()` and runs a dedicated sub-loop for each milestone. Each sub-loop SHALL call `decide_next_step()` to select the next tool, wrap the result in a transient `PlanStep`, and delegate execution to `SkillExecutor._execute_step()`.

#### Scenario: Milestone completes normally
- **WHEN** the Executor sub-loop for a milestone receives a `final_answer` action from `decide_next_step()`
- **THEN** the sub-loop terminates for that milestone
- **AND** execution continues with the next milestone in the list
- **AND** the `final_answer` text is passed to context compression before being forwarded

#### Scenario: Milestone hits iteration budget
- **WHEN** the sub-loop iteration count reaches `milestone.iteration_budget`
- **THEN** `decide_next_step()` is called one final time with the max-iterations flag set
- **AND** the returned `final_answer` (even if partial) is used as the milestone result
- **AND** the outer loop proceeds to the next milestone

#### Scenario: Milestone step triggers retry via Reflect verdict
- **WHEN** `SkillExecutor._execute_step()` returns a `retry` verdict for a tool call
- **THEN** the step is retried up to `_MAX_RETRIES` times within the milestone sub-loop
- **AND** the retry is transparent to the outer milestone loop (iteration count does not advance on retry)

### Requirement: Sub-loop context is isolated per milestone
The `decide_next_step()` calls within a milestone sub-loop SHALL receive only the tool history for the **current** milestone plus compressed summaries of completed milestones, not the full raw history of all prior milestones.

#### Scenario: Second milestone receives compressed first milestone context
- **WHEN** milestone 1 (data fetch) completes and milestone 2 (analysis) begins
- **THEN** the `tool_history` passed to milestone 2's `decide_next_step()` is empty (fresh start)
- **AND** a `prior_context` field containing the compressed milestone 1 summary is injected into the user message

#### Scenario: Milestone sub-loop does not leak tool history across milestones
- **WHEN** milestone 1 called `vector_search` three times
- **THEN** milestone 2's `decide_next_step()` prompt does NOT contain the raw `vector_search` results
- **AND** milestone 2 correctly avoids re-calling `vector_search` with the same args

### Requirement: `SkillExecutor._execute_step()` is used in the primary execution path
The primary `free_agent` execution path (formerly `_dynamic_execute_loop()`) SHALL delegate individual step execution to `SkillExecutor._execute_step()` rather than re-implementing tool invocation inline in `shell.py`.

#### Scenario: Auto-fix fires on run_python failure in primary path
- **WHEN** a `run_python` tool call fails with exit_code != 0 in the milestone sub-loop
- **THEN** `SkillExecutor._auto_fix_python()` is invoked automatically
- **AND** the fix attempt is visible in the Rich output (existing print_info messages)

#### Scenario: Reflect verdict causes milestone step to abort
- **WHEN** `_execute_step()` returns an `abort` verdict
- **THEN** the milestone sub-loop terminates immediately
- **AND** the outer loop marks that milestone as failed and proceeds to the next milestone
