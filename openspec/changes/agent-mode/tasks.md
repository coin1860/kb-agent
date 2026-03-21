## 1. Multi-LLM Provider Infrastructure

- [x] 1.1 Add `LLMProvider` and `LLMRoles` Pydantic models to `config.py`
- [x] 1.2 Add `llm_providers` and `llm_roles` fields to `Settings` class with backward-compatible defaults
- [x] 1.3 Implement auto-migration logic: detect old `llm_api_key/llm_base_url/llm_model` and convert to single "default" provider
- [x] 1.4 Create `LLMRouter` class in new `src/kb_agent/llm_router.py` with `get(role)`, `strong`, `base`, `fast` properties
- [x] 1.5 Refactor `_build_llm()` in `agent/nodes.py` to use `LLMRouter` instead of direct `ChatOpenAI` construction
- [x] 1.6 Update TUI Settings to support multi-provider configuration (Provider list + Role assignment UI)
- [x] 1.7 Write tests for config migration (old format → new format) and LLMRouter role dispatch

## 2. Agent Mode Module Skeleton

- [x] 2.1 Create `src/kb_agent/agent_mode/` package with `__init__.py`
- [x] 2.2 Define `AgentTaskState` TypedDict in `agent_mode/state.py` with all fields from spec
- [x] 2.3 Create `agent_mode/graph.py` with LangGraph topology: goal_intake → plan → act → reflect → human_intervene → finalize
- [x] 2.4 Implement routing functions: `route_after_plan`, `route_after_reflect` with conditional edges
- [x] 2.5 Create stub node functions in `agent_mode/nodes.py` (return pass-through state)

## 3. Skill System

- [x] 3.1 Implement `SandboxContext` class in `agent_mode/sandbox.py` with path validation and permission table
- [x] 3.2 Implement `SkillLoader` class in `agent_mode/skills.py` with `scan()`, `invoke()`, and docstring parsing
- [x] 3.3 Create `__manifest__.json` generation in `SkillLoader.scan()`
- [x] 3.4 Create built-in skills in `agent_mode/builtin_skills/`: `search_kb.py`, `read_file.py`, `jira_query.py`, `confluence_query.py`, `write_output.py`
- [x] 3.5 Implement `run_script` skill with subprocess execution, timeout, and stdout/stderr capture
- [x] 3.6 Implement `ensure_venv` skill with venv creation and pip install support
- [x] 3.7 Write tests for SandboxContext (allowed paths, denied paths, write to read-only)
- [x] 3.8 Write tests for SkillLoader (valid skill loading, invalid skill skipping, manifest generation)

## 4. Session Management

- [x] 4.1 Define `Session` dataclass in `agent_mode/session.py` with id, goal, status, plan, checkpoint, etc.
- [x] 4.2 Implement `SessionManager` class with `create()`, `list_all()`, `switch_to()`, `checkpoint()`, `resume()`
- [x] 4.3 Implement JSON serialization/deserialization for `AgentTaskState` checkpoint
- [x] 4.4 Create `sessions/` directory management (auto-create on first use)
- [x] 4.5 Create `agent_tmp/session_{id}/` workspace directory management (scripts/, drafts/)
- [x] 4.6 Write tests for SessionManager (create, list, checkpoint, resume, switch)

## 5. Agent Graph Nodes (Core Logic)

- [x] 5.1 Implement `goal_intake_node`: parse user goal with strong LLM, produce goal_analysis
- [x] 5.2 Implement `plan_node`: generate multi-step plan with skill assignments using strong LLM
- [x] 5.3 Implement `act_node`: execute current step's skill via SkillLoader.invoke() with SandboxContext
- [x] 5.4 Implement `reflect_node`: evaluate step result, decide next action (next_step / retry / replan / human / finalize)
- [x] 5.5 Implement `human_intervene_node`: call LangGraph `interrupt()` with human_prompt, receive user input
- [x] 5.6 Implement `finalize_node`: summarize results, write final output to `output/session_{id}/`
- [x] 5.7 Implement tiered confirmation logic in `act_node` (Tier 0: auto, Tier 1: notify, Tier 2: interrupt for approval)
- [x] 5.8 Wire up SessionManager.checkpoint() call after each reflect_node completion

## 6. Engine Integration

- [x] 6.1 Add `start_task(goal, on_event)` method to `Engine` class
- [x] 6.2 Add `resume_task(session_id, on_event)` method to `Engine` class
- [x] 6.3 Initialize `SessionManager` and `SkillLoader` in Engine constructor
- [x] 6.4 Compile agent graph in Engine (alongside existing RAG graph)
- [x] 6.5 Create Data Folder sub-directories (`skills/`, `output/`, `agent_tmp/`, `sessions/`) on first Agent Mode use

## 7. Agent Mode TUI

- [x] 7.1 Add Agent Mode tab to TUI with Tab key switching between Chat and Agent modes
- [x] 7.2 Create Agent Mode layout: goal banner, execution log (left), plan panel (right), reflection area
- [x] 7.3 Add Agent Mode command palette with `/new`, `/sessions`, `/status`, `/pause`, `/resume`, `/abort`, `/replan`, `/skills`
- [x] 7.4 Implement `/new` command: prompt for goal, call `Engine.start_task()`
- [x] 7.5 Implement `/sessions` command: list sessions, allow selection to switch/resume
- [x] 7.6 Implement plan panel with real-time status icons (✅ 🔄 ⬜ ❌ ⏭)
- [x] 7.7 Implement execution log with timestamped entries and emoji indicators
- [x] 7.8 Implement intervention modal for human-in-the-loop prompts
- [x] 7.9 Implement Tier 2 confirmation modal (Approve/Deny/Edit) for write operations
- [x] 7.10 Implement `/pause` and `/resume` commands for session control
- [x] 7.11 Implement user message injection during agent execution (proactive intervention)

## 8. Testing & Integration

- [x] 8.1 End-to-end test: create session → plan → act (built-in skill) → reflect → finalize
- [x] 8.2 End-to-end test: consecutive failures → human intervention → resume
- [x] 8.3 End-to-end test: session checkpoint → restart → resume from checkpoint
- [x] 8.4 Integration test: Agent uses RAG search_kb skill to answer sub-question
- [x] 8.5 Integration test: Sandbox denies write outside Data Folder
- [x] 8.6 Test LLMRouter with multiple providers and role switching
- [x] 8.7 Run existing unit tests (`pytest tests/`) to ensure no regression in RAG Mode
- [x] 8.8 Update existing unit tests if required by config or routing changes

## 9. Agent Mode UI Polish

- [x] 9.1 Update `StatusBar` to show "Agent Mode" in blue/cyan when switching mode
- [x] 9.2 Update `watch_chat_mode` to set `#editor-box` border to blue/cyan in Agent Mode
- [x] 9.3 Add `AGENT_WELCOME` message to `tui.py` with instructions
- [x] 9.4 Ensure `AGENT_WELCOME` is displayed in the Agent Mode execution log on first switch
