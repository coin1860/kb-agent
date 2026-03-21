## ADDED Requirements

### Requirement: Agent Mode Tab
The TUI SHALL provide a separate "Agent" tab alongside the existing "Chat" tab, switchable via Tab key.

#### Scenario: Tab switching
- **WHEN** user presses Tab key
- **THEN** TUI cycles between Chat/KB mode and Agent mode, updating the command palette and display panels accordingly

### Requirement: Agent Mode Layout
The Agent Mode tab SHALL display: a goal section, an execution log panel, a plan panel, and a reflection display area.

#### Scenario: Agent Mode UI displayed
- **WHEN** user switches to Agent Mode tab
- **THEN** TUI shows a split layout with execution log on the left and plan/reflection on the right, plus a goal banner at the top

### Requirement: Agent Mode Commands
The Agent Mode command palette SHALL include: `/new`, `/sessions`, `/status`, `/pause`, `/resume`, `/abort`, `/replan`, `/skills`, `/help`.

#### Scenario: Agent command palette
- **WHEN** user types `/` in Agent Mode
- **THEN** command palette shows agent-specific commands instead of RAG commands

### Requirement: Plan Display
The plan panel SHALL display all steps with their status icons: ✅ done, 🔄 running, ⬜ pending, ❌ failed, ⏭ skipped.

#### Scenario: Plan updates in real-time
- **WHEN** a step changes status during execution
- **THEN** the plan panel updates the corresponding step's icon and highlights the current step

### Requirement: Execution Log Stream
The execution log SHALL display timestamped entries for each agent action, including skill invocations, results, errors, and reflections.

#### Scenario: Log entry added
- **WHEN** a skill executes or reflect node produces output
- **THEN** a timestamped entry is appended to the execution log panel with appropriate emoji indicators

### Requirement: Intervention Modal
The TUI SHALL display a modal dialog when the agent requests human input, showing the prompt, context, and input field.

#### Scenario: Intervention modal shown
- **WHEN** `needs_human_input` is set to True by the agent
- **THEN** TUI displays a modal with the agent's prompt, options if provided, and a text input field for the user's response

### Requirement: Tier 2 Confirmation Modal
The TUI SHALL display a confirmation dialog for Tier 2 write operations showing operation details and Approve/Deny/Edit options.

#### Scenario: Write confirmation displayed
- **WHEN** agent attempts a Tier 2 operation (e.g., create Jira issue)
- **THEN** TUI shows a modal with operation type, details preview, and three buttons: Approve, Deny, Edit

### Requirement: Agent Mode UI Branding
The Agent Mode SHALL use a blue (cyan) color scheme for its status indicators and data frame borders to distinguish it from Chat/KB modes.

#### Scenario: Status bar updates to blue
- **WHEN** user switches to Agent Mode
- **THEN** the status bar shows "Agent Mode" in cyan (blue) and the input box border changes to cyan.

### Requirement: Agent Mode Welcome Message
The Agent Mode SHALL display a welcome message providing a quick English explanation of how to use the mode.

#### Scenario: Welcome message shown
- **WHEN** user switches to Agent Mode
- **THEN** the Agent Mode displays a welcome message with instructions and commands in the execution log.
