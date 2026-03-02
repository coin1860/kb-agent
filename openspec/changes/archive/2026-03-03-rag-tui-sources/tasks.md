## 1. Engine & State Refactoring

- [x] 1.1 Update `kb_agent/agent/state.py` (if necessary) to ensure `final_answer` and `sources` can be distinct outputs.
- [x] 1.2 Update `kb_agent/agent/nodes.py:tool_node` to embed the score directly into the `[SOURCE:...]` tag (e.g., `[SOURCE:path:L1:S0.95]`).
- [x] 1.3 Update `kb_agent/agent/nodes.py:synthesize_node` to extract source paths, lines, and scores from the context.
- [x] 1.4 Update `kb_agent/agent/nodes.py:synthesize_node` to return a separate `sources` list in the dictionary and remove the plain-text `Sources:` footer appending logic.
- [x] 1.5 Update `kb_agent/engine.py:Engine.answer_query` to return a tuple `(answer, sources)` instead of just a string.

## 2. History Management Fixes

- [x] 2.1 Update `kb_agent/tui.py:KBAgentApp._run_query` to only append the textual `answer` to `self.chat_history`, omitting structured metadata.

## 3. TUI Interactive Sources

- [x] 3.1 Update `kb_agent/tui.py:KBAgentApp._run_query` to format the received `sources` into Textual action links (e.g., `[@click=show_source(0)]📄 filename (95%)[/]`) and append them to the `RichLog`.
- [x] 3.2 Create a new `SourceDetailScreen(ModalScreen)` in `kb_agent/tui.py` that can display the full markdown content of a referenced source chunk.
- [x] 3.3 Implement the `action_show_source(self, index: int)` method in `KBAgentApp` to push the `SourceDetailScreen` with the correct source text.

## 4. Verification

- [x] 4.1 Run unit tests (e.g., `pytest tests/`) and fix any breakages caused by changing `answer_query`'s return type.
- [x] 4.2 Manually test a RAG query in the TUI to verify the action links appear and the modal opens on click.
- [x] 4.3 Manually test a multi-turn conversation in the TUI to ensure the LLM does not repeat the previous turn's sources.
