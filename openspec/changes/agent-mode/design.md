## Context

kb-agent is a LangGraph-based RAG system with Textual TUI, supporting Jira, Confluence, local file, and ChromaDB-backed vector search. The current architecture is single-turn Q&A: user asks a question → agent retrieves context → synthesizes answer.

The codebase has:
- `agent/` module with a 6-node LangGraph (analyze_and_route → plan → tool_exec → rerank → grade_evidence → reflect → synthesize)
- `tools/` with vector_search, grep_search, read_file, jira_fetch, confluence_fetch, web_fetch, local_file_qa, csv_query
- `engine.py` as public API (mode: "knowledge_base" or "normal")
- `tui.py` (Textual app, ~1600 lines) with settings modals, command palette, status bar
- `config.py` with single-LLM settings (llm_api_key, llm_base_url, llm_model)

Key constraint: the existing RAG pipeline must remain untouched. Agent Mode is an additive, parallel system.

## Goals / Non-Goals

**Goals:**
- Build an autonomous Plan-Act-Reflect task execution loop as a new LangGraph
- Implement a skill system that auto-loads Python scripts from a configurable directory
- Sandbox skill execution to Data Folder boundaries with per-path read/write permissions
- Support multi-session management with checkpoint/resume persistence
- Implement human-in-the-loop via LangGraph `interrupt()` with tiered confirmation
- Replace single-LLM config with multi-provider registry and role-based routing (strong/base/fast)
- Add Agent Mode tab to TUI with plan display, execution log, and intervention UI

**Non-Goals:**
- Replacing or modifying the existing RAG pipeline — it continues as-is
- OS-level sandboxing (Docker, firejail) — Phase 1 uses Python path validation
- Real-time collaboration or multi-user support
- Cloud deployment or remote agent execution
- Building a plugin marketplace or skill sharing platform (Phase 1)

## Decisions

### 1. Separate `agent_mode/` Module (not extending `agent/`)

**Decision**: Create a new `src/kb_agent/agent_mode/` module rather than extending the existing `agent/` RAG module.

**Rationale**: The RAG pipeline and Agent Mode have fundamentally different state schemas, graph topologies, and execution semantics. RAG is a single-invocation Q&A pipeline; Agent Mode is an open-ended loop. Mixing them would create coupling and complexity.

**Alternatives considered**:
- Extending `agent/graph.py` with conditional branches → rejected: would make the already complex 1500-line `nodes.py` unmanageable
- Subclassing AgentState → rejected: TypedDict doesn't support inheritance cleanly

### 2. JSON File Persistence for Sessions (not SQLite)

**Decision**: Use JSON files in `sessions/` directory for session persistence.

**Rationale**: Consistent with existing `config.py` pattern (JSON config). Human-readable for debugging. No additional dependencies. Sufficient for expected volume (< 100 active sessions).

**Alternatives considered**:
- SQLite → deferred to Phase 2 if query performance becomes an issue
- LangGraph built-in checkpointing → explored but requires specific store backends that add complexity

### 3. Path Validation Sandbox (not OS-level isolation)

**Decision**: Implement sandbox as a Python-level `SandboxContext` class that validates all file paths against a permission table before any I/O operation.

**Rationale**: Sufficient for single-user desktop use. No platform-specific dependencies (firejail unavailable on macOS). Fast and simple. Skills are user-authored, so trust boundary is different from untrusted code.

**Alternatives considered**:
- Docker containers → too heavy for a TUI desktop app
- macOS `sandbox-exec` → brittle, poorly documented, would lock to macOS
- Python `RestrictedPython` → too restrictive, breaks many standard library imports

### 4. Multi-LLM Provider with Role-Based Routing

**Decision**: Introduce `LLMProvider` and `LLMRoles` models in config. An `LLMRouter` class maps roles (strong/base/fast) to provider/model pairs. Backward-compatible with single-LLM config.

**Rationale**: Agent Mode's plan/reflect nodes need stronger reasoning than RAG's simple tool selection. Users want to use fast local models for routine tasks and powerful cloud models for complex reasoning. The opencode project demonstrates this pattern effectively.

**Migration**:
- Old config `{llm_api_key, llm_base_url, llm_model}` auto-converts to single provider named "default" with all roles pointing to same model
- New config `{llm_providers, llm_roles}` takes precedence
- Both formats can coexist during migration

### 5. Skills as Python Files with Convention-Based Interface

**Decision**: Each skill is a `.py` file in `skills/` with a docstring header (name, description, parameters) and an `execute()` function. Loaded via `importlib`.

**Rationale**: Lowest friction for users to create custom skills. No framework overhead. Docstring parsing for metadata avoids separate manifest files. Built-in skills wrap existing tools (vector_search, jira_fetch, etc.).

**Alternatives considered**:
- LangChain `@tool` decorator → too tightly coupled to LangChain's interface
- YAML-defined skills → less powerful, can't express complex logic
- Plugin system with entry points → too much overhead for a desktop app

### 6. Tiered Confirmation for Write Operations

**Decision**: Three confirmation tiers — Tier 0 (auto), Tier 1 (notify), Tier 2 (confirm before execution). Implemented via LangGraph `interrupt()`.

**Rationale**: Balances autonomy with safety. Read operations and tmp writes should never block execution flow. External API writes (Jira, Confluence, Git) require explicit approval. Users can configure tier assignments.

### 7. Human-in-the-Loop via LangGraph `interrupt()`

**Decision**: Use LangGraph's built-in `interrupt()` mechanism in a `human_intervene` node, not custom polling or event queues.

**Rationale**: LangGraph's interrupt cleanly pauses graph execution, persists state, and resumes when input is provided. This integrates naturally with the checkpoint system and avoids reinventing async coordination.

## Risks / Trade-offs

- **[Risk] Sandbox is not bulletproof** → Python path validation can be bypassed by determined code (e.g., `ctypes`, symlinks). Mitigation: Skills are user-authored, not untrusted. Add AST scanning for dangerous patterns (`os.system`, `subprocess.call`, `shutil.rmtree`) as a warning layer.

- **[Risk] LLM plan quality varies wildly** → Agent plans may be nonsensical with weaker models. Mitigation: Require "strong" role model for plan/reflect nodes. Add plan validation heuristics (step count limits, skill existence checks).

- **[Risk] Config migration breaks existing users** → New multi-provider format is very different from current flat settings. Mitigation: Full backward compatibility — old format auto-converts on load. Migration function in config.py. TUI settings UI guides users through new format.

- **[Risk] Session state grows unbounded** → Long-running agents accumulate large execution logs. Mitigation: Configurable log retention. Summarize old steps instead of keeping raw output.

- **[Trade-off] In-process skill execution** → Faster but a skill crash can take down the whole app. Accepted for Phase 1. Phase 2 can add subprocess execution option per skill.

- **[Trade-off] JSON persistence** → Simple but no concurrent access safety. Accepted for single-user desktop use. Phase 2 can migrate to SQLite if needed.

## Open Questions

1. **Git integration scope**: Should `git_commit` skill also handle branching and PR creation? Or keep it minimal (commit only) for Phase 1?
2. **Skill hot-reload**: Should skills be reloaded on every execution, or cached with file-watcher invalidation?
3. **Agent memory across sessions**: Should the agent remember outcomes from previous sessions to avoid repeating mistakes?
