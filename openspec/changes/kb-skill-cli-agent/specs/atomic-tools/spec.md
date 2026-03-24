## ADDED Requirements

### Requirement: write_file atomic tool
The system SHALL provide a `write_file` LangChain `@tool` with parameters: `path` (str, relative to `data_folder`), `content` (str), `mode` (str: `"create" | "overwrite" | "append" | "delete"`). This tool SHALL have `requires_approval = True`. On `delete` mode, `content` is ignored. All write operations SHALL be restricted to paths under `data_folder`. Attempts to write outside `data_folder` SHALL raise an error.

#### Scenario: Create new output file
- **WHEN** agent calls `write_file(path="output/hehe.md", content="# Result", mode="create")`
- **THEN** file is created at `data_folder/output/hehe.md`; requires_approval flag is True

#### Scenario: Path traversal blocked
- **WHEN** agent calls `write_file(path="../../etc/passwd", content="...", mode="overwrite")`
- **THEN** tool raises a `SecurityError` and returns an error result; no file is written

#### Scenario: Delete file
- **WHEN** agent calls `write_file(path="output/old.md", mode="delete")`
- **THEN** the file is deleted if it exists; requires_approval is True

---

### Requirement: run_python atomic tool
The system SHALL provide a `run_python` LangChain `@tool` with parameters: `script_path` (str, path to a script file under `data_folder/python_code/`) and `timeout_seconds` (int, default 60). The tool SHALL execute the script using `subprocess.run` with `cwd` set to the script's parent directory, a `timeout` of `timeout_seconds`, and capture both `stdout` and `stderr`. This tool SHALL have `requires_approval = True`.

#### Scenario: Successful script execution
- **WHEN** agent calls `run_python(script_path="python_code/<run_id>/step_2.py")`
- **THEN** subprocess runs the script; stdout and stderr are captured and returned

#### Scenario: Script exceeds timeout
- **WHEN** script runs longer than `timeout_seconds`
- **THEN** subprocess is terminated; tool returns an error result with `"timeout"` in the message

#### Scenario: Script file not in python_code directory
- **WHEN** `script_path` is outside `data_folder/python_code/`
- **THEN** tool raises a `SecurityError`; no subprocess is spawned

#### Scenario: Script execution logs written
- **WHEN** script completes (success or failure)
- **THEN** stdout and stderr are also written to `<script_path>.log` file alongside the script

---

### Requirement: Two-step code generation flow
When the agent needs to generate and run Python code, it SHALL produce a plan with exactly two sequential steps: (1) `write_file` to write the generated code to `data_folder/python_code/<run_id>/step_N.py`, then (2) `run_python` referencing that file path. The LLM SHALL include the complete Python code in the `write_file` args at plan time.

#### Scenario: Code generation plan has two steps
- **WHEN** user asks "用 Python 计算下一个闰年"
- **THEN** plan contains step 1: `write_file(path="python_code/..../step_1.py", content="<python code>")` and step 2: `run_python(script_path="python_code/..../step_1.py")`
