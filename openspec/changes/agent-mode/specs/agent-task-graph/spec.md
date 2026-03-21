## ADDED Requirements

### Requirement: Agent Task Graph Execution
The system SHALL provide a LangGraph-based task execution pipeline with nodes: `goal_intake`, `plan`, `act`, `reflect`, `human_intervene`, and `finalize`.

#### Scenario: User starts a new agent task
- **WHEN** user issues a goal via `/new` command or Agent Mode input
- **THEN** system creates an `AgentTaskState` and enters the `goal_intake` node which analyzes the user's objective using the strong LLM role

#### Scenario: Planning generates ordered steps
- **WHEN** `goal_intake` completes with a parsed goal
- **THEN** `plan` node generates an ordered list of steps, each specifying a skill name, arguments, description, and status (initially "pending")

### Requirement: Plan-Act-Reflect Loop
The system SHALL execute a loop where `act` runs the current step's skill, then `reflect` evaluates the result and decides the next action.

#### Scenario: Successful step execution
- **WHEN** `act` node executes a skill and the skill returns `status: "success"`
- **THEN** `reflect` node marks the step as "done", increments `current_step_index`, resets `consecutive_failures` to 0, and routes to `act` for the next step

#### Scenario: Step failure triggers retry
- **WHEN** `act` node executes a skill and the skill returns `status: "error"`
- **THEN** `reflect` node increments `consecutive_failures`, analyzes the error, and either retries the same step with adjusted arguments or routes to `plan` for replanning

#### Scenario: All steps completed
- **WHEN** `reflect` determines all plan steps have status "done"
- **THEN** system routes to `finalize` node which summarizes results and writes final output

### Requirement: Dynamic Replanning
The system SHALL support dynamic plan revision during execution.

#### Scenario: Reflect triggers replan
- **WHEN** `reflect` determines the current plan is no longer viable (e.g., missing data, wrong approach)
- **THEN** system routes back to `plan` node with current execution context, and `plan` generates a new plan (incrementing `plan_version`) that accounts for completed steps and new information

### Requirement: Agent Task State
The system SHALL maintain an `AgentTaskState` TypedDict with fields: `session_id`, `goal`, `goal_analysis`, `plan`, `current_step_index`, `plan_version`, `execution_log`, `workspace`, `available_skills`, `consecutive_failures`, `max_consecutive_failures`, `reflection_history`, `needs_human_input`, `human_prompt`, `human_response`, `task_status`, and `status_callback`.

#### Scenario: State tracks execution progress
- **WHEN** each node completes execution
- **THEN** corresponding state fields are updated and an entry is appended to `execution_log`
