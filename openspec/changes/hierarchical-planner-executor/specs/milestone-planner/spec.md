## ADDED Requirements

### Requirement: Decompose user command into ordered milestones
The system SHALL provide a `plan_milestones(command, session, llm, skill_def)` function in `planner.py` that makes a single LLM call to decompose the user's command into an ordered list of 1–5 `Milestone` objects before execution begins.

#### Scenario: Simple command produces single milestone
- **WHEN** the user command is a single-step lookup (e.g., "fetch Jira ticket ABC-123")
- **THEN** `plan_milestones()` returns a list containing exactly one `Milestone` with `goal` describing the fetch and `iteration_budget` of 1

#### Scenario: Multi-step command produces multiple milestones
- **WHEN** the user command requires sequential phases (e.g., "query CSV, analyze data, write report to output/")
- **THEN** `plan_milestones()` returns 2–5 `Milestone` objects in execution order
- **AND** each `Milestone.expected_output` describes an observable result (e.g., "CSV schema and sample rows", "analysis findings list", "path to output/report.md")

#### Scenario: Planner LLM returns empty or invalid response
- **WHEN** the milestone planner LLM call fails or returns 0 valid milestones
- **THEN** `plan_milestones()` returns a single fallback `Milestone` covering the entire original command
- **AND** a warning is logged at DEBUG level

### Requirement: Milestone dataclass fields
The `Milestone` dataclass SHALL have three fields: `goal: str` (human-readable objective), `expected_output: str` (observable completion signal), and `iteration_budget: int` (maximum tool calls for this milestone, defaulting to `cli_max_iterations`).

#### Scenario: Milestone fields are populated from LLM output
- **WHEN** the Planner LLM returns a valid JSON milestone array
- **THEN** each `Milestone` is constructed with all three fields populated from the JSON
- **AND** any milestone missing `iteration_budget` uses `settings.cli_max_iterations` as default

### Requirement: Planner prompt excludes individual tool names
The `MILESTONE_PLANNER_SYSTEM` prompt SHALL describe goal categories and expected output types but SHALL NOT list specific tool names or argument schemas.

#### Scenario: Planner reasoning stays at goal level
- **WHEN** the planner prompt is constructed for a data retrieval + write task
- **THEN** the prompt contains no mention of tool names (e.g., `vector_search`, `write_file`)
- **AND** the resulting milestones describe outcomes, not tool calls
