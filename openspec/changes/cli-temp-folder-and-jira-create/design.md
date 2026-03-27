# Design: CLI Temp Folder & Jira Create Ticket

## Part 1: Temp Folder Architecture

### Data Folder Layout (after change)

```
data_folder/
├── archive/
├── input/           ← user @-picker files
├── index/           ← vector index
├── output/          ← FINAL user deliverables only (.md, .csv, .pdf etc.)
│   └── <run_id>/    ← session-scoped, permanently kept
├── python_code/     ← LLM-generated scripts (cleaned up after task)
│   └── <run_id>/
├── skills/
├── source/
└── temp/            ← NEW: intermediate files between steps
    └── <run_id>/    ← session-scoped, deleted after task completes
```

### config.py Changes

Add `temp_path: Optional[Path]` field, computed in `_compute_paths()` as `data_folder / "temp"`.
Add `jira_default_project: Optional[str]` field for Jira ticket creation fallback.

### Session Changes

`Session.setup_dirs()` gains a third parameter `temp_base: Path`.
Creates `self.temp_dir = temp_base / self.run_id` on start.
`Session.cleanup()` deletes `temp_dir` (alongside existing `python_code_dir` deletion).

### skill_cli.py / shell.py Changes

`shell.start()` passes `settings.temp_path` to `session.setup_dirs()`.
Planner prompt updated so LLM knows: intermediate files → `temp/<filename>`, final files → `output/<filename>`.

### FileTool Changes

**`allowed_paths` expansion:**
```python
# Add to __init__():
if settings.output_path:
    self.allowed_paths.append(settings.output_path.resolve())
if settings.temp_path:
    self.allowed_paths.append(settings.temp_path.resolve())
```

**Basename fallback in `read_file()`:**
When a path is NOT_FOUND, extract `basename = Path(file_path).name` and search:
```
Priority order:
  1. data_folder/temp/**/basename    (most likely — LLM just wrote it here)
  2. data_folder/output/**/basename
  3. data_folder/input/basename
  4. data_folder/source/**/basename
  5. data_folder/index/**/basename
```
Within each directory, sort matches by `mtime` descending (most recent first).
Return content of first match found. If no match anywhere, return original NOT_FOUND.

### write_file Tool Docstring Update

Add path convention documentation to the `write_file` tool docstring so the LLM planner
generates correct paths:
- Intermediate/temp files → `temp/<filename>`
- Final output → `output/<filename>`

## Part 2: Jira Create Ticket

### JiraConnector.create_issue()

New method on `JiraConnector`:
```python
def create_issue(
    self,
    project_key: str,
    summary: str,
    description: str = "",
    issue_type: str = "Task",
) -> Dict[str, Any]:
```

Calls `self.jira.create_issue(fields={...})` and returns a dict with:
- `key`: e.g. `"KB-456"`
- `url`: browse URL
- `summary`, `project`, `issue_type`
- On error: `{"error": True, "content": "<error message>"}`

Falls back to `settings.jira_default_project` if `project_key` is empty string.
If still empty after fallback, returns an error asking user to provide project key.

### @tool jira_create_ticket

New tool in `agent/tools.py`:

```python
@tool
def jira_create_ticket(
    summary: str,
    description: str = "",
    project_key: str = "",
    issue_type: str = "Task",
) -> str:
```

**Inline approval flow inside the tool:**
1. Resolve `project_key` via setting fallback
2. If still empty: return error message asking for project key
3. Print ticket summary to console using `rich`
4. Prompt user `[Y/n]` via `input()`
5. If confirmed: call `JiraConnector().create_issue()`
6. Return JSON result

**Approval display format:**
```
╭─ Create Jira Ticket ─────────────────────────╮
│  Project:     KB                              │
│  Type:        Task                            │
│  Summary:     Fix login bug                   │
│  Description: Users report login fails...     │
╰───────────────────────────────────────────────╯
Create this ticket? [Y/n]:
```

Tool is added to `ALL_TOOLS` so it is available in both CLI and RAG mode.
No changes to `SKILL_TOOL_APPROVAL_REGISTRY` — approval is handled inline.
