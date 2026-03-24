## ADDED Requirements

### Requirement: Startup banner
On launch, the system SHALL print a Rich-styled banner displaying: application name (`KB-Skill Agent`), number of skills loaded, active data folder path, and a brief usage hint.

#### Scenario: Banner on startup
- **WHEN** `kb-skill` is launched
- **THEN** a formatted banner is printed before the first prompt

---

### Requirement: Plan table display
Before execution (auto-approve or manual approve), the system SHALL display the execution plan as a Rich `Table` with columns: `#` (step number), `Tool`, `Description`, `Approval` (✓ or 🔒).

#### Scenario: Plan table rendered
- **WHEN** a plan is generated
- **THEN** a table shows all steps with correct columns; write/run steps show 🔒 in Approval column

---

### Requirement: Think/Act/Observe/Reflect log rendering
During execution, each phase SHALL be rendered with a distinct color and prefix:
- **💭 Think** (dim/gray): LLM reasoning text
- **🔧 Act** (cyan): Tool name and args
- **📄 Observe** (green for success, red for error): Result summary
- **🔁 Reflect** (yellow): LLM self-evaluation verdict and reason

#### Scenario: Step renders all four phases
- **WHEN** a step completes normally
- **THEN** four distinct log lines appear in the correct colors and order

#### Scenario: Error in Observe phase
- **WHEN** a tool returns an error
- **THEN** Observe is rendered in red with the error message

---

### Requirement: Progress bar for multi-item operations
When a plan contains 3 or more steps, the system SHALL display a Rich `Progress` bar showing current step number and total steps (e.g., `Step 2/5`).

#### Scenario: Progress bar with 5-step plan
- **WHEN** a 5-step plan is executing
- **THEN** a progress bar `Step 1/5 → Step 2/5 → ...` updates as steps complete

#### Scenario: No progress bar for short plans
- **WHEN** a plan has 1 or 2 steps
- **THEN** no progress bar is shown (avoids clutter for simple commands)

---

### Requirement: Final result display
After all steps complete, the system SHALL print a formatted result panel using Rich `Markdown` rendering if the result is markdown, or a `Panel` with plain text otherwise. Output file paths SHALL be highlighted.

#### Scenario: Markdown result rendered
- **WHEN** the final step produces a markdown document
- **THEN** it is rendered as Rich Markdown in the terminal

#### Scenario: Output file path highlighted
- **WHEN** a `write_file` step succeeds
- **THEN** the output file path is printed in a highlighted style (e.g., bold cyan)

---

### Requirement: Interrupt menu display
When `Ctrl+C` is pressed, the system SHALL print a pause notice showing the current step, then a prompt: `[s]kip / [r]eplan / [c]ontinue / [q]uit`.

#### Scenario: Interrupt menu appears
- **WHEN** Ctrl+C fires during step 2 of 4
- **THEN** `⏸ Paused at Step 2/4` is printed, followed by the option prompt
