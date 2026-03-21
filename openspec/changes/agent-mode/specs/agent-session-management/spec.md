## ADDED Requirements

### Requirement: Session Creation
The system SHALL create a new session with a unique ID, goal, timestamp, and initial status when the user starts an agent task.

#### Scenario: New session via /new command
- **WHEN** user types `/new` followed by a goal description in Agent Mode
- **THEN** system creates a `Session` object with a UUID, stores it in `sessions/` directory, and sets it as the active session

### Requirement: Session Listing and Switching
The system SHALL list all persisted sessions and allow switching between them.

#### Scenario: List sessions
- **WHEN** user types `/sessions` in Agent Mode
- **THEN** system displays a list of all sessions with ID, goal summary, status, and last updated timestamp

#### Scenario: Switch to existing session
- **WHEN** user selects a session from the list
- **THEN** system loads the session's checkpoint, restores `AgentTaskState`, and displays previous execution history in the TUI

### Requirement: Checkpoint Persistence
The system SHALL automatically checkpoint the `AgentTaskState` after each `reflect` node completion.

#### Scenario: Auto-checkpoint after reflect
- **WHEN** `reflect` node completes and updates the state
- **THEN** system serializes the current `AgentTaskState` to JSON and writes it to `sessions/session_{id}.json`

#### Scenario: Resume from checkpoint
- **WHEN** user switches to a previously paused session
- **THEN** system deserializes the checkpoint JSON, reconstructs `AgentTaskState`, and resumes execution from `current_step_index`

### Requirement: Session Status Tracking
The system SHALL track session status as one of: `active`, `paused`, `completed`, `failed`.

#### Scenario: Session transitions
- **WHEN** a session is running, paused by user, all steps completed, or max failures exceeded
- **THEN** session status transitions to `active`, `paused`, `completed`, or `failed` respectively

### Requirement: Session Workspace Isolation
Each session SHALL have its own workspace directory under `agent_tmp/session_{id}/`.

#### Scenario: Session workspace created
- **WHEN** a new session is created
- **THEN** system creates `agent_tmp/session_{id}/` with sub-directories: `scripts/`, `drafts/`
