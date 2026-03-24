## ADDED Requirements

### Requirement: Launch interactive REPL shell
The system SHALL provide a `kb-skill` CLI entrypoint that starts a persistent interactive shell session. On launch, it SHALL load all skill playbooks from `data_folder/skills/*.yaml`, display a startup banner showing the number of skills loaded and the active data folder path, and then present a prompt (`kb-skill> `) for user input.

#### Scenario: Normal launch
- **WHEN** user runs `kb-skill` with a valid `data_folder` configured
- **THEN** the shell starts, prints a banner (skill count, data folder path), and displays the prompt

#### Scenario: No skills directory
- **WHEN** `data_folder/skills/` does not exist
- **THEN** the shell starts with 0 skills loaded, displays a warning, and continues to the prompt

#### Scenario: Launch with --data-folder override
- **WHEN** user runs `kb-skill --data-folder /custom/path`
- **THEN** settings data_folder is overridden and skills are loaded from `/custom/path/skills/`

---

### Requirement: Session identity and manifest
The system SHALL create a unique session run ID (UUID4) on every `kb-skill` launch. A session manifest SHALL be written to `data_folder/output/<run_id>/_manifest.json` on first command execution. The manifest SHALL record: `run_id`, `started_at` (ISO8601), `skill_name` (null if free-agent), `status` (`active|completed|aborted`), `steps` array, `output_dir`, `python_code_dir`. Status SHALL be updated to `completed` or `aborted` on exit.

#### Scenario: Manifest created on first execution
- **WHEN** user submits the first command in a session
- **THEN** `_manifest.json` is written to `output/<run_id>/`

#### Scenario: Manifest updated on clean exit
- **WHEN** user exits with `exit` or `quit`
- **THEN** manifest `status` is updated to `completed` and `ended_at` is set

#### Scenario: Manifest updated on abort
- **WHEN** user presses `Ctrl+C` and selects `[q]uit`
- **THEN** manifest `status` is updated to `aborted`

---

### Requirement: Built-in shell commands
The system SHALL support the following built-in commands that do NOT go through the LLM:
- `help` or `?`: list available skills and built-in commands
- `skills`: display a table of all loaded skills (name, description, file)
- `exit` / `quit`: cleanly exit the shell

#### Scenario: Help command
- **WHEN** user types `help` or `?`
- **THEN** a Rich-formatted table is printed listing skills and builtins; NO LLM call is made

#### Scenario: Skills command
- **WHEN** user types `skills`
- **THEN** a table shows all loaded skills: name, 1-line description, YAML filename

#### Scenario: Exit command
- **WHEN** user types `exit` or `quit`
- **THEN** session manifest is finalized and the process exits cleanly

---

### Requirement: Prompt with command history (single session)
The system SHALL use `prompt_toolkit` or Python's `readline` to provide up-arrow command history within a session. History SHALL NOT persist across sessions in this version (future multi-session extension point).

#### Scenario: Up-arrow history
- **WHEN** user presses the up-arrow key at the prompt
- **THEN** the previous command in the current session is recalled

---

### Requirement: Session design extensible for multi-session
The `Session` data class and manifest format SHALL be defined such that future multi-session support can be added by implementing a session index loader without changing the manifest schema. The shell SHALL not store any state in global variables — all state SHALL live in the `Session` object.

#### Scenario: Single active session per process
- **WHEN** `kb-skill` is running
- **THEN** there is exactly one `Session` object instantiated, with all state encapsulated within it
