## ADDED Requirements

### Requirement: Execute plan steps sequentially with Think/Act/Observe/Reflect rendering
The system SHALL execute plan steps one at a time. For each step, the executor SHALL: (1) emit a **Think** log entry describing the agent's reasoning, (2) invoke the tool (**Act**), (3) emit an **Observe** log entry with the result summary (**Observe**), (4) invoke the LLM to self-evaluate whether the step result is sufficient or needs retry (**Reflect**). The reflect LLM call SHALL return `{"verdict": "continue" | "retry" | "abort", "reason": "..."}`.

#### Scenario: Successful step execution
- **WHEN** a step's tool returns a non-error result
- **THEN** Think, Act, Observe, Reflect log entries are printed in order; verdict is `continue`; executor moves to next step

#### Scenario: Step tool returns error
- **WHEN** a tool call returns an error or raises an exception
- **THEN** Observe entry shows the error; Reflect verdict is `retry` or `abort`; executor handles accordingly

#### Scenario: Reflect verdict is retry
- **WHEN** reflect LLM returns `{"verdict": "retry"}`
- **THEN** the executor re-runs the step (max 2 retries before marking failed and continuing)

---

### Requirement: Cancellation token checked at every step boundary
The system SHALL maintain a `CancellationToken` (wrapping `threading.Event`). Before executing each new step, the executor SHALL check if the token is set. If set, execution pauses and the interrupt menu is presented.

#### Scenario: Ctrl+C between steps
- **WHEN** user presses Ctrl+C and the executor is between two steps
- **THEN** current step is not started; interrupt menu appears immediately

#### Scenario: Ctrl+C during tool execution
- **WHEN** user presses Ctrl+C while a synchronous tool call is blocking
- **THEN** the token is set; after the blocking call returns (or times out), the executor checks the token and presents the interrupt menu before starting the next step

---

### Requirement: Interrupt menu options
When execution is paused (Ctrl+C), the system SHALL present: `[s]kip / [r]eplan / [c]ontinue / [q]uit`.
- `[s]kip`: mark current step as skipped; continue with next step
- `[r]eplan`: prompt user for a re-plan instruction; invoke planner with remaining steps + instruction; present approval gate for revised tail plan
- `[c]ontinue`: resume from current step
- `[q]uit`: abort session; update manifest status to `aborted`

#### Scenario: Skip current step
- **WHEN** user presses Ctrl+C and selects `s`
- **THEN** current step is marked `skipped`; execution continues from the next step

#### Scenario: Replan after interrupt
- **WHEN** user presses Ctrl+C mid-execution and selects `r`
- **THEN** user is prompted for a re-plan instruction; revised plan (for remaining steps) is shown; approval gate fires; on `a` execution resumes from new plan

#### Scenario: Continue without change
- **WHEN** user presses Ctrl+C and selects `c`
- **THEN** execution resumes exactly where it was interrupted

#### Scenario: Quit on interrupt
- **WHEN** user presses Ctrl+C and selects `q`
- **THEN** manifest is updated to `aborted`; shell prompt returns

---

### Requirement: Audit trail written per step
The system SHALL append each executed step's record to the session manifest steps array: `{step_number, tool, args, status, started_at, ended_at, result_summary}`. Status SHALL be one of: `done | failed | skipped | retried`.

#### Scenario: Step completes successfully
- **WHEN** a step finishes
- **THEN** its record in the manifest shows `status: done`, `started_at`, `ended_at`

#### Scenario: Step is skipped
- **WHEN** user skips a step via interrupt
- **THEN** its record shows `status: skipped`

---

### Requirement: run_python subprocess kill on interrupt
When a `run_python` step is actively executing a subprocess and `Ctrl+C` fires, the system SHALL call `process.terminate()` on the subprocess before presenting the interrupt menu.

#### Scenario: Terminate long-running Python script
- **WHEN** a Python subprocess is running and user presses Ctrl+C
- **THEN** `process.terminate()` is called; subprocess ends; interrupt menu is shown
