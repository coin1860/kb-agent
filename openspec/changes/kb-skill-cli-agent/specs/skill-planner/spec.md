## ADDED Requirements

### Requirement: Generate numbered execution plan
Given a user command and optional skill playbook content, the system SHALL invoke the LLM to produce a structured execution plan as a JSON array. Each plan step SHALL contain: `step_number` (int), `description` (str), `tool` (str), `args` (dict), `requires_approval` (bool).

#### Scenario: Free-agent plan for read-only task
- **WHEN** user enters "搜索 shane 是谁" with no skill match
- **THEN** planner generates a plan like `[{"step_number":1,"description":"Semantic search for shane","tool":"vector_search","args":{"query":"shane 个人信息"},"requires_approval":false}]`

#### Scenario: Skill-driven plan
- **WHEN** user command matches a skill with 3 intent steps
- **THEN** planner generates ≥3 steps, each with a concrete tool and args derived from skill content + current context

#### Scenario: Plan includes write_file step
- **WHEN** user says "搜索 shane 是谁，结果存到 output/hehe.md"
- **THEN** plan includes at least one step with `tool="write_file"` and `requires_approval=true`

---

### Requirement: Approval gate based on plan content
The system SHALL inspect the generated plan before presenting it to the user. If ALL steps have `requires_approval=false`, the plan SHALL be auto-approved and execution starts immediately. If ANY step has `requires_approval=true`, the system SHALL display the plan table and prompt: `[a]pprove / [e]dit / [q]uit`.

#### Scenario: Auto-approve read-only plan
- **WHEN** plan contains only `vector_search`, `jira_fetch`, `read_file` steps
- **THEN** plan is displayed and execution starts without waiting for user input

#### Scenario: Approval required for write operation
- **WHEN** plan contains a `write_file` step
- **THEN** plan table is displayed and user must enter `a`, `e`, or `q`

#### Scenario: User quits at approval
- **WHEN** user enters `q` at the approval prompt
- **THEN** execution is cancelled, prompt returns

---

### Requirement: Edit plan via natural language re-instruction
When user selects `[e]dit` at the approval prompt, the system SHALL prompt for a natural language instruction describing the desired change. The system SHALL invoke the LLM with the current plan + the edit instruction and produce a revised plan. The revised plan SHALL be displayed and the approval gate SHALL repeat.

#### Scenario: User edits plan via instruction
- **WHEN** user selects `e` and types "只搜索 In Progress 的 Jira 票"
- **THEN** planner is reinvoked with original plan + instruction, returns revised plan
- **AND** approval gate repeats with revised plan

#### Scenario: Edit produces same plan
- **WHEN** edit instruction does not meaningfully change the plan
- **THEN** revised plan is still displayed; user can approve or edit again

---

### Requirement: Skill YAML loader and template expansion
The system SHALL load skill YAML files from `data_folder/skills/` on startup. Each skill YAML SHALL support optional `context` variables with `{{variable}}` placeholder syntax (Jinja2-style). At planning time, context variables SHALL be resolved from the environment (date, configured project key, etc.) before the playbook is passed to the planner LLM.

#### Scenario: Valid skill loaded
- **WHEN** `data_folder/skills/weekly-jira-report.yaml` exists with valid YAML
- **THEN** it is available in the skill index with its name and description

#### Scenario: Invalid skill YAML
- **WHEN** a skill file has malformed YAML
- **THEN** it is skipped with a warning; other skills are loaded normally

#### Scenario: Template variable resolution
- **WHEN** a skill contains `{{date}}` in a step description
- **THEN** at planning time `{{date}}` is replaced with the current date string before the LLM sees the skill content
