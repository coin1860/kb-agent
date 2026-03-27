# Tasks: CLI Temp Folder & Jira Create Ticket

## Part 1: Temp Folder & File Path Fallback

- [x] **Task 1**: Add `temp_path` and `jira_default_project` fields to `config.py`
  - Add `temp_path: Optional[Path]` to `Settings`
  - Add `jira_default_project: Optional[str]` to `Settings`
  - In `_compute_paths()`: compute `temp_path = data_folder / "temp"` (or `~/.kb-agent/temp`)
 
- [x] **Task 2**: Update `Session` to manage `temp_dir` lifecycle
  - Add `temp_dir: Optional[Path]` field to `Session` dataclass
  - Update `setup_dirs(output_base, python_code_base, temp_base)` to create `temp_base / run_id`
  - Update `cleanup()` to `shutil.rmtree(self.temp_dir)` alongside python_code_dir
  - Update `_to_dict()` to include `temp_dir`

- [x] **Task 3**: Pass `temp_path` through `shell.py` → `session.setup_dirs()`
  - In `SkillShell.__init__()`: store `temp_path` from settings
  - In `shell.start()` / `_run_command()`: pass `temp_path` to `session.setup_dirs()`
  - Create `temp_path.mkdir(parents=True, exist_ok=True)` in `skill_cli.py` startup

- [x] **Task 4**: Expand `FileTool.allowed_paths` and add basename fallback
  - In `FileTool.__init__()`: append `output_path` and `temp_path` to `allowed_paths`
  - In `FileTool.read_file()`: after NOT_FOUND, call new `_data_folder_fallback(basename)`
  - Implement `_data_folder_fallback(basename)`: search `temp/**/`, `output/**/`, `input/`, `source/**/`, `index/**/` in order; return content of most-recently-modified match, or `None`

- [x] **Task 5**: Update `write_file` docstring with path conventions
  - Add to docstring: "Use `temp/<filename>` for intermediate files between steps. Use `output/<filename>` for final user-requested deliverables."

## Part 2: Jira Create Ticket

- [x] **Task 6**: Add `JiraConnector.create_issue()` method
  - Method signature: `create_issue(project_key, summary, description="", issue_type="Task") -> Dict`
  - Fallback `project_key` to `settings.jira_default_project` if empty
  - Return error dict if `project_key` still empty
  - Call `self.jira.create_issue(fields={...})` and return `{key, url, summary, project, issue_type}`
  - Handle and return API errors gracefully

- [x] **Task 7**: Add `@tool jira_create_ticket` to `agent/tools.py`
  - Tool args: `summary: str`, `description: str = ""`, `project_key: str = ""`, `issue_type: str = "Task"`
  - Resolve `project_key` from arg or `settings.jira_default_project`
  - Display rich-formatted ticket summary panel
  - Prompt `[Y/n]` via `input()` for inline approval
  - On `Y`: call `_get_jira().create_issue(...)` and return JSON result
  - On `n`: return `{"status": "cancelled", "message": "Ticket creation cancelled by user."}`
  - Add tool to `ALL_TOOLS` list

## Part 3: Testing & Verification

- [x] **Task 8**: Fix existing test failure in `tests/agent/test_plan_layer.py`
  - Update confluence_fetch regex test cases to use 9-10 digit IDs

- [x] **Task 9**: Create unit tests for Temp Folder logic
  - Test `Session.setup_dirs()` creates `temp/` folder
  - Test `Session.cleanup()` removes `temp/` folder
  - Test `FileTool.read_file()` fallback logic finds files in `temp/`

- [x] **Task 10**: Create unit tests for Jira Ticket Creation
  - Test `JiraConnector.create_issue()` with and without default project
  - Test `jira_create_ticket` tool with mocked approval (Y/n)

- [x] **Task 11**: Run all existing tests to ensure no regressions
  - Execute `pytest` and verify 100% pass rate
