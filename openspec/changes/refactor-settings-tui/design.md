## Context

The UI configuration page of `kb-agent` is growing rapidly. Flat hierarchies are unintuitive for dense configurations, so we are shifting towards a two-layer categorization structure. The immediate challenge is adapting existing models and migrating any live users (though backwards compatibility can be as simple as migrating valid flat config values to their nested blocks upon initialization, or simply resetting).

## Goals / Non-Goals

**Goals:**
- Separate settings into natural groups.
- Maintain Pydantic validation across nested models.
- Implement a two-level interactive menu in the TUI (Category Selection -> Detail Editing).

**Non-Goals:**
- Completely overhauling how config is persisted (it will remain as `kb-agent.json`).
- Developing a full config migration parser from `v1` to `v2` (we will do a best effort initialization from flat attributes if nested ones are missing).

## Decisions

**Decision 1: JSON Schema Redesign**
Introduce distinct Pydantic models: `LLMSettings`, `RAGSettings`, `AtlassianSettings`, `GeneralSettings`.
The parent `Settings` object will compose these four models as optional attributes.

**Decision 2: TUI Navigation Control**
Introduce `SettingsCategoryScreen(ModalScreen)` representing Level 1 grouping. Upon selecting a category via `up`/`down` and `Enter`, the model delegates to a dynamic `SettingsDetailScreen(ModalScreen[bool])` populated uniquely based on the category passed. Upon exit from Detail Screen, save the state and return to Category Screen until ESC is hit.

**Decision 3: Best-Effort Migration**
The `load_settings()` code will read JSON. If the file is structured natively, great. If not, it will synthesize the new structures by aggregating the flat keys into the nested sub-models, then persist back using the new structure.

## Risks / Trade-offs

- **Risk**: Missed variable references in the codebase will crash components like the agent or RAG loops.
  **Mitigation**: Run exhaustive `grep` across the codebase to ensure all `config.settings.XXX` endpoints map faithfully to their new properties (e.g. `config.settings.llm.model`, `config.settings.atlassian.jira_url`).
