## Why

The current kb-agent is a powerful RAG system for knowledge retrieval, but it is limited to single-turn Q&A — it answers a question and stops. Users increasingly need an autonomous agent that can execute multi-step tasks: analyze data across multiple sources, generate reports, create Jira tickets, update Confluence pages, and even write and execute Python scripts. This evolution from "knowledge retrieval" to "task automation" is the natural next step, inspired by systems like OpenDevin and SWE-Agent.

## What Changes

- **New `agent_mode/` module**: A complete Plan-Act-Reflect LangGraph pipeline for autonomous multi-step task execution
- **Skill system**: Auto-loading skill scripts from a configurable `skills/` directory with a sandbox that restricts file access to the Data Folder
- **Session management**: Multi-session support with JSON-based persistence, checkpoint/resume, and TUI commands (`/new`, `/sessions`, `/status`, `/pause`, `/resume`, `/abort`)
- **Human-in-the-loop**: Agent pauses and requests user input on consecutive failures or uncertain decisions; tiered confirmation for write operations (Jira/Confluence/Git)
- **Multi-LLM provider architecture**: Replace single LLM config with a provider registry and role-based routing (strong/base/fast models for different tasks)
- **Data Folder restructuring**: Add `skills/`, `output/`, `agent_tmp/`, `sessions/` sub-directories with per-path permission controls
- **Agent Mode TUI tab**: Separate tab for Agent Mode with plan display, execution log, and intervention controls
- **Write-capable skills**: New skills for creating Jira issues, updating Confluence pages, Git commits, and executing sandboxed Python scripts

## Capabilities

### New Capabilities
- `agent-task-graph`: Plan-Act-Reflect LangGraph pipeline for autonomous multi-step task execution with dynamic replanning
- `agent-skill-system`: Auto-loading skill scripts from `skills/` directory with sandbox path validation, venv management, and dynamic script execution
- `agent-session-management`: Multi-session persistence with JSON checkpoints, session listing, switching, pause/resume support
- `agent-human-in-the-loop`: Tiered confirmation system (auto/notify/confirm) and LangGraph interrupt-based human intervention when agent is stuck
- `multi-llm-provider`: Provider registry with role-based routing (strong/base/fast) replacing single LLM config, with backward compatibility
- `agent-tui`: Agent Mode TUI tab with plan panel, execution log, reflection display, and intervention controls

### Modified Capabilities
- `configuration`: Add `llm_providers`, `llm_roles`, and agent-mode settings (Data Folder sub-paths, sandbox config); backward-compatible with existing single-LLM config
- `routing-engine`: Add `mode="agent"` branch in Engine to dispatch to agent graph alongside existing RAG graph

## Impact

- **config.py**: Major refactor of LLM settings section — new `LLMProvider` and `LLMRoles` models, migration logic for old config format
- **engine.py**: Add `start_task()`, `resume_task()` methods; integrate SessionManager and SkillLoader
- **tui.py**: Add Agent Mode tab, new command palette entries, plan/execution panels, intervention modals
- **Dependencies**: No new major dependencies (LangGraph already used; `importlib` for skill loading is stdlib)
- **Data Folder**: New sub-directories created on first Agent Mode use; existing RAG data untouched
- **Existing RAG pipeline**: Unchanged — RAG Mode continues to work as-is in its own tab
