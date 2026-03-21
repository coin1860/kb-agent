## ADDED Requirements

### Requirement: Consecutive Failure Intervention
The system SHALL pause execution and request human input when consecutive failures exceed `max_consecutive_failures` (default: 3).

#### Scenario: Agent stuck after repeated failures
- **WHEN** `consecutive_failures` reaches `max_consecutive_failures` in `reflect` node
- **THEN** system sets `needs_human_input = True`, generates a `human_prompt` describing the failures and options, and routes to `human_intervene` node

#### Scenario: Human provides guidance
- **WHEN** user responds to the intervention prompt
- **THEN** `human_intervene` node stores the response in `human_response`, resets `needs_human_input`, and routes back to `reflect` for re-evaluation with the user's input

### Requirement: LangGraph Interrupt Mechanism
The system SHALL use LangGraph's `interrupt()` function in the `human_intervene` node to pause graph execution until user input is received.

#### Scenario: Graph pauses at interrupt
- **WHEN** `human_intervene` node calls `interrupt(prompt)`
- **THEN** LangGraph pauses execution, persists state, and the TUI displays the prompt to the user

#### Scenario: Graph resumes after input
- **WHEN** user provides input via the TUI intervention interface
- **THEN** LangGraph resumes the `human_intervene` node with the user's input as the return value of `interrupt()`

### Requirement: Tiered Confirmation for Write Operations
The system SHALL enforce a tiered confirmation model for skill operations with side effects.

#### Scenario: Tier 0 operation executes automatically
- **WHEN** a skill performs a read operation or writes to `agent_tmp/`
- **THEN** system executes the operation without any confirmation

#### Scenario: Tier 1 operation notifies user
- **WHEN** a skill writes a final file to `output/`
- **THEN** system executes the operation and displays a notification in the TUI execution log

#### Scenario: Tier 2 operation requires explicit approval
- **WHEN** a skill attempts to create a Jira issue, update a Confluence page, execute a Git commit, or install a pip package
- **THEN** system pauses execution via `interrupt()`, displays the operation details and asks for user approval (Approve/Deny/Edit), and only proceeds if approved

### Requirement: User Proactive Intervention
The system SHALL allow users to type messages during agent execution to provide guidance or corrections.

#### Scenario: User intervenes during execution
- **WHEN** user types a message in the Agent Mode input while the agent is executing
- **THEN** system pauses execution at the next checkpoint, injects the user's message into `human_response`, and routes to `reflect` for re-evaluation
