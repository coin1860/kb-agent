## 1. Foundation & Config

- [x] 1.1 Add `skills_path`, `output_path`, `python_code_path` optional fields to `config.py` Settings, derived from `data_folder` (e.g., `data_folder/skills`, `data_folder/output`, `data_folder/python_code`)
- [x] 1.2 Add `typer>=0.12` to `pyproject.toml` dependencies and add `kb-skill = "kb_agent.skill_cli:main"` to `[project.scripts]`
- [x] 1.3 Create directory skeleton: `src/kb_agent/skill/__init__.py`, `src/kb_agent/tools/atomic/__init__.py`

## 2. Atomic Tools

- [x] 2.1 Implement `src/kb_agent/tools/atomic/file_ops.py`: `write_file` `@tool` with `path`, `content`, `mode` params; path-traversal guard (must be under `data_folder`); `requires_approval` tracked in TOOL_APPROVAL_REGISTRY
- [x] 2.2 Implement `src/kb_agent/tools/atomic/code_exec.py`: `run_python` `@tool` with `script_path`, `timeout_seconds` params; `subprocess.run` with cwd, timeout, stdout/stderr capture; writes `.log` file; path guard; `requires_approval` tracked in TOOL_APPROVAL_REGISTRY
- [x] 2.3 Update `src/kb_agent/agent/tools.py`: add `get_skill_tools()`, `SKILL_TOOL_APPROVAL_REGISTRY`, `tool_requires_approval()`; all existing tools default to False

## 3. Skill Loader & Session Model

- [x] 3.1 Implement `src/kb_agent/skill/loader.py`: `SkillDef` dataclass (name, description, file_path, raw_content); `load_skills(skills_path) -> dict[str, SkillDef]`; skip malformed YAML with warning; Jinja2 template variable expansion (`{{date}}`, etc.)
- [x] 3.2 Implement `Session` dataclass in `src/kb_agent/skill/session.py`: fields `run_id` (UUID4), `started_at`, `skill_name`, `status`, `steps`, `output_dir`, `python_code_dir`; `write_manifest()` and `update_manifest()` methods writing to `output/<run_id>/_manifest.json`

## 4. Intent Router

- [x] 4.1 Implement `src/kb_agent/skill/router.py`: `route_intent(command, skills, llm) -> RouteResult`; build compressed skill index (name + ≤15-word description per skill); LLM call returning `{"route": "skill"|"free_agent", "skill_id": "..."}` JSON; fallback to `free_agent` on parse failure with audit warning

## 5. Skill Planner

- [x] 5.1 Implement `src/kb_agent/skill/planner.py`: `generate_plan(command, skill_def, session, llm) -> list[PlanStep]`; `PlanStep` dataclass with `step_number`, `description`, `tool`, `args`, `requires_approval`; system prompt includes SKILL_TOOLS descriptions + tool approval flags
- [x] 5.2 Implement `replan(current_plan, remaining_steps, edit_instruction, llm) -> list[PlanStep]` in `planner.py` for the Ctrl+C `[r]eplan` path

## 6. Skill Renderer

- [x] 6.1 Implement `src/kb_agent/skill/renderer.py`: `SkillRenderer` class wrapping `rich.console.Console`; `print_banner(skill_count, data_folder)`, `print_plan_table(steps)`, `print_think(text)`, `print_act(tool, args)`, `print_observe(result, is_error)`, `print_reflect(verdict, reason)` methods with correct colors/prefixes
- [x] 6.2 Add `print_progress(current, total)` using `rich.progress.Progress` (shown only when total ≥ 3 steps)
- [x] 6.3 Add `print_result(content)` using `rich.markdown.Markdown` for markdown results; `rich.panel.Panel` for plain text; highlight output file paths in bold cyan
- [x] 6.4 Add `print_interrupt_menu(step_number, total)` method showing pause notice and `[s]kip / [r]eplan / [c]ontinue / [q]uit` prompt

## 7. Skill Executor

- [x] 7.1 Implement `src/kb_agent/skill/interruptor.py`: `CancellationToken` wrapping `threading.Event`; `InterruptHandler` that registers `SIGINT` signal handler and sets the token; `check()` method that returns True if cancellation requested
- [x] 7.2 Implement core `src/kb_agent/skill/executor.py`: `SkillExecutor` class; `execute_plan(plan, session, tool_map, llm, renderer, cancel_token)` method; per-step Think→Act→Observe→Reflect loop; step retry logic (max 2 retries on `retry` verdict); cancellation token check at every step boundary; manifest step record append on each step completion/skip/failure
- [x] 7.3 Add `run_python` subprocess termination in `InterruptHandler` — store active subprocess reference; call `process.terminate()` on interrupt before showing menu

## 8. Shell REPL & CLI Entry

- [x] 8.1 Implement `src/kb_agent/skill/shell.py`: `SkillShell` class; `start()` method with `while True` REPL loop; built-in command handling (`help`, `skills`, `exit`/`quit`); `session_history` list (in-memory, current session only); readline for up-arrow history within session
- [x] 8.2 Implement `src/kb_agent/skill_cli.py`: Typer app with `main()` function; `--data-folder` optional override; instantiate shell and call `start()`; wire together: `load_settings()` → `load_skills()` → `SkillShell(skills, renderer, llm)` → `shell.start()`
- [x] 8.3 Wire approval gate in shell: after `generate_plan()`, inspect steps for `requires_approval`; if all False → auto-approve; if any True → `renderer.print_plan_table()` + prompt `[a/e/q]`; handle `e` → `replan()` → repeat gate

## 9. Integration & Sample Skills

- [x] 9.1 Create `data_folder/skills/` directory placeholder and `source/skills/weekly-jira-report.yaml` sample skill with name, description, context vars, and 3 intent steps
- [x] 9.2 Create `source/skills/kb-search-and-save.yaml` sample skill: search RAG and save result to output file
- [ ] 9.3 End-to-end smoke test: `kb-skill` starts, loads skills, routes "搜索 shane 是谁 存到 output/test.md", shows plan, auto-approves (read) + approves write, executes, writes file, prints result

## 10. Tests

- [x] 10.1 Unit test `skill/loader.py`: valid YAML loads correctly, malformed YAML is skipped, template variables are expanded
- [x] 10.2 Unit test `skill/router.py`: skill match returned for close command, free_agent returned for generic command, graceful fallback on LLM parse failure
- [x] 10.3 Unit test `tools/atomic/file_ops.py`: path traversal blocked, file created/overwritten/deleted correctly, `requires_approval=True`
- [x] 10.4 Unit test `tools/atomic/code_exec.py`: stdout captured, timeout triggers termination, path guard works
- [x] 10.5 Unit test approval gate logic: all-read plan auto-approves, plan-with-write requires approval
