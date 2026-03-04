## 1. Update Core Configuration

- [ ] 1.1 Redefine Pydantic models in `src/kb_agent/config.py` to create nested `LLMSettings`, `RAGSettings`, `AtlassianSettings`, and `GeneralSettings`.
- [ ] 1.2 Update the root `Settings` object to compose these nested models.
- [ ] 1.3 Add backwards-compatible initialization logic in `load_settings()` to read legacy flat configurations and convert them to the new schema before saving. Update `.env` parsing mapping.

## 2. Refactor Codebase References

- [ ] 2.1 Update variable accesses in `src/kb_agent/tui.py` (e.g., `config.settings.llm_model` -> `config.settings.llm.model`).
- [ ] 2.2 Update variable accesses in `src/kb_agent/agent/nodes.py`.
- [ ] 2.3 Update variable accesses in `src/kb_agent/engine.py` and `src/kb_agent/llm.py`.
- [ ] 2.4 Update variable accesses in `src/kb_agent/chunking.py`, `src/kb_agent/cli.py`, and `src/kb_agent/audit.py`.

## 3. TUI Settings Screen Overhaul

- [ ] 3.1 Create `SettingsCategoryScreen` with LLM, RAG, Atlassian, and General options, driven by ↑↓ input and Enter.
- [ ] 3.2 Create `SettingsDetailScreen` that dynamically renders fields for the chosen category and captures updates.
- [ ] 3.3 Replace the flat `SettingsScreen` implementation in `tui.py` with these two components and ensure the `on_button_pressed` save logic preserves the full nested `config.settings` structure.
