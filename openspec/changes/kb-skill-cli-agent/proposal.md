## Why

`kb-agent` excels at interactive Q&A via its TUI, but has no way to execute multi-step, automatable tasks — such as generating a Jira weekly report, running an ad-hoc data analysis, or scripting a knowledge-base audit. A new `kb-skill` interactive CLI shell fills this gap: it gives power users a geek-friendly command prompt where an LLM agent plans and executes tasks, leveraging all existing connectors (Jira, Confluence, ChromaDB, file ops) plus new atomic tools (file write, Python code generation/execution).

## What Changes

- **New command entrypoint** `kb-skill`: an interactive REPL shell (non-fullscreen, scrolling terminal) separate from the existing TUI.
- **New `skill/` package** under `src/kb_agent/`: intent router, planner, executor, renderer, and interrupt handler.
- **New atomic tools**: `write_file` (creates/modifies/deletes output files), `run_python` (generates and sandboxed-executes Python scripts).
- **New `/skills/` directory** under `data_folder`: YAML-format skill playbooks loaded at startup. LLM matches user intent to a skill or falls back to free-agent planning.
- **New `/output/` and `/python_code/` directories** under `data_folder`: timestamped, traceable outputs for every session execution.
- **Plan approval gate**: after every command, the agent shows a numbered execution plan. Write/delete operations require explicit user approval (`a/e/q`); read-only plans auto-approve.
- **Live interrupt handling** (`Ctrl+C`): pause mid-execution and choose to skip the current step, re-plan with new instructions, continue, or quit.
- **Config extension**: `skills_path`, `output_path`, `python_code_path` derived from `data_folder`.
- **No breaking changes** to existing TUI, RAG graph, or Engine.

## Capabilities

### New Capabilities

- `kb-skill-shell`: The interactive REPL shell entrypoint — session management, prompt loop, and command history scaffold designed for future multi-session/resume support.
- `skill-intent-router`: LLM-based router that, on each user command, classifies intent as skill-matched (loads playbook) or free-agent (LLM self-plans), using compressed skill metadata.
- `skill-planner`: Translates user intent + optional skill playbook into a numbered, reviewable execution plan (`[{step, tool, args, requires_approval}]`).
- `skill-executor`: Step-by-step executor with interrupt support (`threading.Event` cancellation token), re-plan-on-interrupt, and manifest/audit trail writing.
- `skill-renderer`: Rich-based CLI renderer — plan tables, Think/Act/Observe/Reflect log panels, progress bars for multi-item loops, and final result formatting.
- `atomic-tools`: `write_file` and `run_python` LangChain tools with `requires_approval=True` flag; code written to `/python_code/<run_id>/` before execution.

### Modified Capabilities

- `agent-tools`: Extend `agent/tools.py` with `SKILL_TOOLS = ALL_TOOLS + [write_file, run_python]`. No modification to existing `ALL_TOOLS`.

## Impact

- **New dependency**: `typer>=0.12` (CLI framework; `rich` already present).
- **`pyproject.toml`**: new `kb-skill = "kb_agent.skill_cli:main"` script entry.
- **`config.py`**: three new optional path fields, derived from `data_folder`.
- **`agent/tools.py`**: additive change only — new `SKILL_TOOLS` list and two new `@tool` functions.
- **No changes** to `tui.py`, `engine.py`, `agent/graph.py`, `agent/nodes.py`, or existing connector/tool files.
