## Why

The current TUI `/settings` page is a huge, single-page form with 15+ input fields covering everything from LLM configuration to Atlassian tokens. This makes the UI cluttered and hard to navigate or manage. Additionally, `kb-agent.json` currently uses a flat structure that does not reflect natural groupings of settings. We need a two-level navigation system for the settings UI and a nested structure for the JSON configuration to keep settings well-organized and scalable.

## What Changes

- Modify `kb-agent.json` to use a nested schema (groups: `llm`, `rag`, `atlassian`, `general`).
- Group `embedding` settings under the `llm` category.
- Combine `Storage` and `Advanced` settings into a new `general` category.
- Refactor the TUI `SettingsScreen` into:
    - Level 1 (`SettingsCategoryScreen`): A menu to select settings categories (LLM, RAG, Atlassian, General) using keyboard ↑↓ and Enter.
    - Level 2 (`SettingsDetailScreen`): A dedicated form showing only the fields for the selected category.
- Update `config.Settings` (Pydantic models) to reflect the new nested dictionary structure, and ensure backwards compatibility/migration from the old flat format if possible (or just require a new setup/overwrite).
- Update all references to `config.settings.xxx` across the application to correctly use the nested paths (e.g., `config.settings.llm.model`).

## Capabilities

### New Capabilities
None.

### Modified Capabilities
- `tui-settings`: The setting page UI and UX is completely changing.
- `configuration`: The underlying data structure for the configuration is becoming nested.

## Impact

- `src/kb_agent/config.py`: Major refactor of Pydantic models.
- `src/kb_agent/tui.py`: Major UI refactor for the Settings flow.
- Multiple files referencing `config.settings` (e.g., `agent/nodes.py`, `chunking.py`, `engine.py`, `llm.py`, `cli.py`).
