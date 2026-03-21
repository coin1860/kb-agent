## ADDED Requirements

### Requirement: Skill Auto-Loading
The system SHALL auto-scan and load all `.py` files from the configured `skills/` directory on startup, excluding files starting with `_`.

#### Scenario: Skills directory scanned on startup
- **WHEN** the Agent Mode is initialized
- **THEN** `SkillLoader` scans `skills/` directory, parses each skill's docstring header for metadata (name, description, parameters), and registers them in an in-memory registry

#### Scenario: Skill manifest generated
- **WHEN** skill scanning completes
- **THEN** system writes a `__manifest__.json` file to `skills/` listing all discovered skills with their metadata

### Requirement: Skill Convention Interface
Each skill file SHALL expose an `execute(**kwargs) -> dict` function and a docstring header with `name`, `description`, and `parameters` fields.

#### Scenario: Valid skill loaded
- **WHEN** a `.py` file in `skills/` contains a docstring with `name:` and `description:` fields and an `execute()` function
- **THEN** `SkillLoader` successfully registers it as an available skill

#### Scenario: Invalid skill skipped
- **WHEN** a `.py` file in `skills/` lacks the required docstring header or `execute()` function
- **THEN** `SkillLoader` logs a warning and skips it without crashing

### Requirement: Sandbox Path Validation
The system SHALL validate all file I/O paths against a permission table before execution, restricting access to the Data Folder.

#### Scenario: Read from allowed read-only path
- **WHEN** a skill attempts to read a file from `index/`, `source/`, `.chroma/`, or `skills/`
- **THEN** system allows the read operation

#### Scenario: Write to allowed writable path
- **WHEN** a skill attempts to write a file to `output/` or `agent_tmp/`
- **THEN** system allows the write operation

#### Scenario: Access outside Data Folder denied
- **WHEN** a skill attempts to access any path outside the Data Folder root
- **THEN** system raises `SandboxViolationError` with a descriptive message

#### Scenario: Write to read-only path denied
- **WHEN** a skill attempts to write to `index/`, `source/`, or `skills/`
- **THEN** system raises `SandboxViolationError` indicating the path is read-only

### Requirement: Dynamic Script Execution
The system SHALL support Agent-generated Python scripts written to `agent_tmp/session_{id}/scripts/` and executed in a subprocess.

#### Scenario: Script execution in sandbox
- **WHEN** Agent generates a Python script for a task step
- **THEN** system writes the script to `agent_tmp/session_{id}/scripts/`, executes it via subprocess with cwd set to the session workspace, and captures stdout/stderr

#### Scenario: Script execution timeout
- **WHEN** a script exceeds the configured timeout (default: 30 seconds)
- **THEN** system terminates the subprocess and returns an error result to the reflect node

### Requirement: Virtual Environment Management
The system SHALL support creating and using a per-session Python virtual environment for `pip install` operations.

#### Scenario: Venv created on demand
- **WHEN** a skill step requires a Python package not available in the base environment
- **THEN** system creates a venv at `agent_tmp/session_{id}/.venv` if it does not exist, installs the package, and uses the venv for script execution

#### Scenario: Venv reused across steps
- **WHEN** multiple steps within the same session require the venv
- **THEN** system reuses the existing venv without recreating it

### Requirement: Built-in Skills
The system SHALL provide built-in skills that wrap existing RAG tools: `search_kb` (vector_search), `read_file` (file_tool), `jira_query` (jira_fetch), `confluence_query` (confluence_fetch), `write_output` (new: write to output/).

#### Scenario: Built-in skill invoked
- **WHEN** Agent plan references a built-in skill name
- **THEN** system delegates to the corresponding existing tool implementation with sandbox validation
