# Agent Mode Architecture Exploration

> **Date**: 2026-03-21
> **Author**: Shane H SHOU
> **Status**: Exploration / Pre-proposal

## 1. Overview

This document captures the architecture exploration for evolving kb-agent from a RAG-only system into an autonomous task-processing Agent (Agent Mode), inspired by OpenDevin/SWE-Agent.

### Current System

```
TUI (Textual) ──→ Engine ──→ LangGraph (RAG Mode)
  │                              │
  ├── /clear, /jira, /file...   ├── analyze_and_route
  ├── Settings Modal             ├── plan_node
  ├── CommandPalette             ├── tool_exec
  └── StatusBar                  ├── rerank_node
                                 ├── grade_evidence
                                 ├── reflect_node
                                 └── synthesize_node
```

### Target System

```
TUI (Textual)
  ├── [Tab: Chat/KB]  → Existing RAG Pipeline (unchanged)
  └── [Tab: Agent]    → NEW Agent Mode Pipeline
                           ├── goal_intake (LLM: strong)
                           ├── plan_node   (LLM: strong)
                           ├── act_node    (Skills execution)
                           ├── reflect_node (LLM: strong)
                           ├── human_intervene (interrupt)
                           └── finalize_node
```

---

## 2. Core Requirements

### 2.1 File System Integration (Data Folder Structure)

- Pre-configured Data Folder root directory
- Sub-folders: `skills/`, `output/`, `agent_tmp/`, `sessions/`
- Auto-scan and load skills on startup
- Sandbox: skills restricted to Data Folder paths only

### 2.2 Multi-Session Management

- TUI commands: `/new`, `/sessions`, `/status`, `/pause`, `/resume`, `/abort`
- Each session preserves full task state
- Support pause/resume with checkpoint persistence

### 2.3 Task Execution Loop (Plan-Act-Reflect)

- Autonomous planning from user goal
- Skill invocation based on plan steps
- Self-reflection and plan adjustment on errors
- Maximum consecutive failure threshold triggers human intervention

### 2.4 Human-in-the-Loop

- Agent pauses and requests input when stuck
- User can intervene at any time during execution
- Real-time display of thinking/planning/execution/reflection

---

## 3. Key Design Decisions

### 3.1 Skill Sandbox

Skills operate within a **Path Validation Layer** sandbox:

| Path | Permission | Purpose |
|------|-----------|---------|
| `.chroma/` | READ ONLY | Vector database queries |
| `index/` | READ ONLY | Processed document index |
| `source/` | READ ONLY | Raw source documents |
| `skills/` | READ ONLY | Skill scripts themselves |
| `output/` | READ+WRITE | Final deliverables |
| `agent_tmp/` | READ+WRITE | Temp files, scripts, logs |
| `sessions/` | READ+WRITE | Session persistence |
| Outside Data Folder | ❌ DENIED | SandboxViolationError |

**Special Permissions:**
- `pip install` → allowed only within `agent_tmp/.venv`
- subprocess → allowed only for scripts in `agent_tmp/scripts/`
- Network → only through existing connectors (Jira/Confluence/Web)

**Dynamic Script Execution:**
- Agent can generate Python scripts and write to `agent_tmp/session_X/scripts/`
- Scripts execute in subprocess with cwd limited to session workspace
- Configurable timeout (default: 30s)
- Per-session venv created on demand

### 3.2 RAG vs Agent Separation

RAG and Agent are **separate modes** (tabs in TUI):
- **RAG Mode**: Single Q&A, read-only, no side effects
- **Agent Mode**: Multi-step tasks, can create files/tickets/commits

Agent Mode can invoke RAG as a sub-skill (`rag_query`).

**Write Skills (Agent Mode Only):**

| Skill | Side Effect | Confirmation Tier |
|-------|------------|-------------------|
| `write_file` | Create/modify files in output/ or agent_tmp/ | Tier 0: Auto |
| `create_jira_issue` | Create Jira ticket | Tier 2: Confirm |
| `update_confluence` | Edit Confluence page | Tier 2: Confirm |
| `git_commit` | Git add + commit (+ push?) | Tier 2: Confirm |
| `run_script` | Execute generated Python script | Tier 1-2: Context-dependent |
| `pip_install` | Install packages to session venv | Tier 2: Confirm |

**Confirmation Tiers:**
- **Tier 0 (Auto)**: No confirmation needed (reads, tmp writes)
- **Tier 1 (Notify)**: Notify but don't block (output writes)
- **Tier 2 (Confirm)**: Must approve before execution (external API calls, installs)

### 3.3 Multi-LLM Architecture

Inspired by opencode — multiple LLM providers with role-based routing:

**Provider Registry:**
```json
{
  "llm_providers": [
    {"name": "local-qwen", "base_url": "http://localhost:1234/v1", "api_key": "local", "models": ["qwen3-30b-a3b"]},
    {"name": "groq", "base_url": "https://api.groq.com/openai/v1", "api_key": "gsk_xxx", "models": ["deepseek-r1-distill-llama-70b", "llama-3.3-70b-versatile"]}
  ],
  "llm_roles": {
    "strong": "groq/deepseek-r1-distill-llama-70b",
    "base": "local-qwen/qwen3-30b-a3b",
    "fast": "groq/llama-3.3-70b-versatile"
  }
}
```

**Role Assignment:**

| Task | Role | Rationale |
|------|------|-----------|
| RAG: analyze_route | base | Simple classification |
| RAG: plan_node | base | Tool selection |
| RAG: synthesize | strong | Final answer quality |
| Agent: goal_intake | strong | Complex intent understanding |
| Agent: plan_node | strong | Multi-step reasoning |
| Agent: reflect_node | strong | Deep reflection |
| Agent: code_gen | strong | Python script generation |
| Shared: query_decompose | fast/base | Quick decomposition |

**Backward Compatibility:**
- Old single-LLM config auto-converts to single provider with all roles pointing to same model
- New multi-provider config takes precedence if both exist

---

## 4. Agent LangGraph Topology

```
START
  │
  ▼
goal_intake ──→ plan ──→ act ──→ reflect ──┬──→ act (next step)
                  ▲                         ├──→ plan (replan)
                  │                         ├──→ human_intervene → reflect
                  │                         └──→ finalize → END
                  │
                  └──── (from reflect: needs replan)
```

### AgentTaskState

```python
class AgentTaskState(TypedDict, total=False):
    session_id: str
    goal: str
    goal_analysis: str
    plan: list[dict[str, Any]]       # Ordered steps
    current_step_index: int
    plan_version: int
    execution_log: list[dict]
    workspace: dict[str, Any]
    available_skills: list[dict]
    consecutive_failures: int
    max_consecutive_failures: int    # Default: 3
    reflection_history: list[str]
    needs_human_input: bool
    human_prompt: str
    human_response: str
    task_status: str                 # planning|executing|reflecting|waiting_human|completed|failed
    status_callback: Any
```

---

## 5. Session Persistence

**Phase 1**: JSON files in `sessions/` directory
**Phase 2**: Optional SQLite migration

Each session checkpointed after every `reflect_node` completion.

```
sessions/
├── session_abc123.json    # Full session state
└── session_def456.json
```

---

## 6. Data Folder Layout

```
Data Folder (configurable root)
├── .chroma/           # Vector DB (existing)
├── source/            # Raw documents (existing)
├── index/             # Processed index (existing)
├── skills/            # Agent skill scripts (NEW)
│   ├── __manifest__.json
│   ├── search_kb.py
│   ├── write_file.py
│   └── custom_skills...
├── output/            # Final deliverables (NEW)
│   └── session_{id}/
├── agent_tmp/         # Temp workspace (NEW)
│   └── session_{id}/
│       ├── scripts/
│       ├── drafts/
│       ├── .venv/
│       └── exec.log
└── sessions/          # Session persistence (NEW)
```

---

## 7. Module Structure

```
src/kb_agent/
├── agent/              # EXISTING RAG pipeline (unchanged)
├── agent_mode/         # NEW Agent Mode module
│   ├── __init__.py
│   ├── graph.py        # Agent task graph
│   ├── nodes.py        # Plan/Act/Reflect nodes
│   ├── state.py        # AgentTaskState
│   ├── skills.py       # SkillLoader + SandboxContext
│   ├── session.py      # SessionManager
│   └── builtin_skills/ # Default skills wrapping existing tools
├── engine.py           # Add mode="agent" branch
├── tui.py              # Add Agent tab
└── config.py           # Add llm_providers, llm_roles
```

---

## 8. Implementation Phases

### Phase 1: Foundation
- AgentTaskState definition
- agent_mode/ module creation
- Plan-Act-Reflect LangGraph
- SkillLoader (basic)
- Built-in Skills (wrap existing tools)
- SessionManager (JSON persistence)
- `/new` and `/sessions` commands

### Phase 2: TUI & Human-in-the-loop
- Agent Mode TUI panel
- Plan real-time display
- Execution log streaming
- Human intervention interaction
- `/pause`, `/resume`, `/abort`

### Phase 3: Polish & Extend
- Custom Skill SDK
- Parallel step support
- Session search/filter
- Execution statistics and reports

---

## 9. Open Questions

1. **Config migration**: How smooth is the automatic migration from old→new LLM config?
2. **Script safety scanning**: AST-level checks for generated scripts (block `os.system`, `shutil.rmtree`, etc.) vs trust sandbox boundary?
3. **Git/GitHub integration**: Built-in skill or user-defined? Which Git operations? (commit, push, PR, branch?)
