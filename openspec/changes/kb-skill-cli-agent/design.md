## Context

`kb-agent` currently provides two modes via its `cli.py` entrypoint: `kb-agent index` (document ingestion) and the default `kb-agent` (Textual TUI full-screen chat). The TUI is optimized for conversational Q&A — interactive, multi-turn, with a rich full-screen Textual layout.

A new class of usage is emerging: **automated task execution** — generating reports, analyzing data, querying multiple systems and writing results to files, or executing ad-hoc Python scripts. These workflows don't fit the conversational Q&A model. They benefit from:
- A scrolling, geek-friendly CLI (not a full-screen TUI)
- An explicit **plan → approve → execute** lifecycle with human oversight
- Reusable **skill playbooks** (YAML) shared across the team
- Atomic tools that produce **auditable, traceable outputs** on disk

The existing `agent/tools.py` already wraps all connectors (Jira, Confluence, ChromaDB, web, file) in LangChain `@tool` decorators, and `agent/nodes.py` already implements the Think→Plan→Execute→Reflect loop for RAG. The new `kb-skill` shell **reuses this infrastructure** rather than reimplementing it.

## Goals / Non-Goals

**Goals:**
- Interactive REPL shell (`kb-skill`) with a Rich-rendered, scrolling non-fullscreen output
- LLM-driven intent routing: match user command to a loaded skill playbook OR fall back to free-agent planning
- Plan review gate: show numbered step plan, auto-approve read-only plans, require explicit approval for write/delete/run-python operations
- Mid-execution interrupt via `Ctrl+C` with `[s]kip / [r]eplan / [c]ontinue / [q]uit` options
- Skill playbooks in YAML loaded from `data_folder/skills/` at startup
- All existing connectors (Jira, Confluence, ChromaDB, web, file-read) available to the skill agent
- New atomic write tools: `write_file`, `run_python` (with approval gate and audit trail)
- Session-scoped execution log written to `data_folder/output/<run_id>/` and `data_folder/python_code/<run_id>/`
- Architecture designed to support future multi-session persistence (but not implemented in this change)

**Non-Goals:**
- Multi-session management or session resume (future)
- Full sandboxing / containerized code execution (subprocess with timeout is sufficient for internal tool)
- Modification of the existing TUI, RAG graph, or Engine
- Streaming LLM responses in the CLI (synchronous invoke is sufficient)
- Natural language skill editing via the CLI (skills are edited as YAML files directly)

## Decisions

### D1: Separate entrypoint (`kb-skill`) rather than subcommand of `kb-agent`

**Decision**: New `[project.scripts]` entry `kb-skill = "kb_agent.skill_cli:main"`.

**Rationale**: The UX is fundamentally different (REPL vs. TUI vs. one-shot). Keeping them separate avoids polluting the existing `cli.py` main argument parser, and makes the command surface cleaner (`kb-skill` vs. `kb-agent skill`). The underlying Python packages are shared.

**Alternative considered**: Adding `skill` as a subcommand to `kb-agent`. Rejected — `kb-agent` already defaults to TUI which is launched with no args; adding subcommands would require a breaking restructure of `cli.py`.

---

### D2: New `skill/` package with its own planner — reuse nodes primitives, not the RAG graph

**Decision**: `src/kb_agent/skill/` contains its own `planner.py`, `executor.py`, `router.py`, `renderer.py`, `interruptor.py`. It **reuses `agent/tools.py` tools directly** but does NOT run the existing LangGraph RAG graph.

**Rationale**: The RAG graph topology (`analyze_and_route → plan → tool_exec → rerank → grade_evidence → reflect → synthesize`) is optimized for Q&A: it assumes a single query and produces a single answer. Skill execution is fundamentally different: it plans multiple named steps across different tool categories, may write files, may run code, and must support mid-execution human intervention at step boundaries. Building a new graph (or a pure Python executor) avoids bending the RAG graph into something it wasn't designed to do.

**Alternative considered**: Extending the LangGraph RAG graph with new nodes. Rejected — would couple skill execution complexity into the RAG flow, making both harder to reason about and maintain.

---

### D3: Intent routing via LLM with compressed skill metadata

**Decision**: On each user command, call the LLM once with a compressed skill index (name + 1-line description per skill) and the user's command. LLM returns: `{route: "skill", skill_id: "..."}` or `{route: "free_agent"}`.

**Rationale**: Semantic matching is always more accurate than keyword matching. Compressing to name + 1-line description keeps the prompt token cost negligible (~50 tokens per skill). A separate pre-filter step would add complexity with marginal benefit at the expected skill count (<20 skills).

**Alternative considered**: Keyword/embedding pre-filter then LLM confirmation. Rejected for initial version — over-engineering for the expected scale.

---

### D4: Auto-approve read-only plans; require explicit approval for write/delete/run

**Decision**: Tools are classified at definition time with a `requires_approval` flag. After generating a plan, the executor checks if any step contains an `approval_required=True` tool. If none: auto-execute. If any: show plan table and prompt `[a]pprove / [e]dit / [q]uit`.

**Rationale**: Forces the user to consciously approve side-effects (file creation/modification/deletion, code execution) while keeping the experience fluid for read-only queries. Aligns with the user's explicit preference.

**Tools that require approval**: `write_file` (create, overwrite, delete modes), `run_python`.
**Tools that do not**: `vector_search`, `jira_fetch`, `jira_jql`, `confluence_fetch`, `web_fetch`, `read_file`, `grep_search`, `local_file_qa`, `csv_info`, `csv_query`.

---

### D5: Interrupt via `threading.Event` cancellation token

**Decision**: A `CancellationToken` (`threading.Event`) is shared between the executor and a `SIGINT` handler. When `Ctrl+C` fires, the event is set; the executor checks the token at each step boundary (before starting a new step). Currently-running synchronous tool calls (e.g., a blocking `requests.get()`) complete before the check — we do not forcibly kill LLM HTTP calls mid-flight.

**Rationale**: Synchronous tool calls are generally fast (<5s). Forcibly terminating mid-request risks corrupted state (e.g., partial Jira writes, incomplete file writes). Checking at step boundaries is safe and predictable.

**Exception**: `run_python`-spawned subprocesses are explicitly `process.terminate()`'d on interrupt, since they may run for tens of seconds.

**Alternative considered**: `asyncio`-based cancellation with task cancellation. Rejected for this version — adds complexity; all existing tools are synchronous.

---

### D6: Code generation is two explicit steps: `write_file` → `run_python`

**Decision**: When the agent needs to generate and run Python code, the plan always contains two explicit steps: (1) `write_file` to save the generated code to `/python_code/<run_id>/step_N.py`, then (2) `run_python` referencing that file path.

**Rationale**: The two-step approach provides a human-readable audit trail, allows the user to inspect generated code during the approval gate, and makes the approval semantics clear (both steps require approval). A unified `code_interpreter` tool would be a black box.

---

### D7: Session data structure designed for future multi-session support

**Decision**: Each `kb-skill` invocation creates a `Session` object with a UUID run ID. Session metadata (skill name, steps, status, artifact paths) is written to `output/<run_id>/_manifest.json` at start and updated on completion/abort. The `SkillShell` REPL holds the single active `Session`.

**Rationale**: Even though multi-session management is out of scope now, designing the data model around a persistent `Session` entity means future resume support requires only adding a session index + loader, not a data migration.

## Risks / Trade-offs

| Risk | Mitigation |
|------|-----------|
| LLM generates a plan with wrong tool args (e.g., wrong Jira query) | User sees the plan before execution; Edit option lets them fix via natural language re-instruction |
| `run_python` executes code with side effects beyond `/python_code/` dir | Sandbox by setting `cwd` to the run's python_code dir; 60s timeout; capture stdout/stderr; approval required |
| Skill YAML format is too rigid and LLM misinterprets step intent | Steps are natural language descriptions, not prescriptive commands. LLM decides tool mapping. |
| Ctrl+C during LLM invocation leaves the session in an unknown state | The executor tracks step status (`pending / running / done / skipped / failed`); interrupting during LLM think phase just cancels the current think — the step stays `pending` and can be retried |
| Token cost of routing + planning adds latency per command | Routing is one small LLM call (~50-100 tokens); planning is one medium call. Acceptable for a productivity tool. |

## Migration Plan

1. No migration needed — purely additive.
2. New `typer` dependency added to `pyproject.toml`.
3. Three new path fields added to `config.py` Settings model (all optional, derived from `data_folder`).
4. New `kb-skill` script entry in `pyproject.toml`.
5. After `uv pip install -e .` (or `pip install -e .`), `kb-skill` becomes available.

## Open Questions

- **Skill template variables**: Should skills support `{{variable}}` substitution (e.g., `{{project}}`, `{{date}}`)? If yes, use Jinja2. Deferred to implementation — the loader can add this as a post-parse step.
- **Command history persistence**: Should the REPL support up-arrow history across sessions? `prompt_toolkit` provides this via `FileHistory`. Recommended for UX but not blocking.
- **Output format of `run_python`**: stdout is captured and included in the step observation. Should it also be written to a `.log` file in the run dir? Recommend yes, for auditability.
