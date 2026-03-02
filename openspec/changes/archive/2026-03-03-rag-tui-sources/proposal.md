## Why

Currently, the RAG agent appends source citations directly as plain text at the end of its response. This causes two main issues:
1. **Unfriendly UI**: Absolute file paths are shown instead of clean filenames, and vector search scores are lost. The flat text format cannot be interacted with to view the actual source chunk.
2. **Multi-turn "Echochamber"**: Because the sources footer is part of the assistant's previous message text, it gets fed back into the LLM context during multi-turn conversations. This confuses the LLM, often causing it to re-state the previous turn's sources unnecessarily.

By decoupling sources from the LLM textual answer and rendering them as interactive UI elements, we solve the multi-turn hallucination problem and greatly improve the user experience.

## What Changes

- **Option A Architecture Refactor**: The LangGraph RAG workflow (`synthesize_node`) will return the answer string and a structured list of sources separately, rather than appending the sources to the answer string.
- The `Engine.answer_query` API will return a standardized response object (or tuple) containing both the answer text and the structured sources metadata.
- **TUI Updates**:
  - The TUI's `_run_query` will process the structured sources and render them as clickable Action Links in the `RichLog` (e.g., `[@click=show_source(0)]📄 filename.txt (95%)[/]`).
  - Implement an `action_show_source(index)` handler in the TUI to pop up a `ModalScreen` displaying the full text of the cited chunk.
  - Convert ChromaDB L2 distance scores to human-readable similarity percentages (e.g., `95%`).
- **History Fix**: The TUI history will only store the textual `answer`, ensuring the sources metadata is permanently stripped from the LLM's multi-turn conversational context.

## Capabilities

### New Capabilities
- `rag-interactive-sources`: Interactive source citations in the TUI with clickable popups and human-readable similarity scores.

### Modified Capabilities
- `rag-response`: Redefining how RAG responses are returned from the engine (structured payload vs plain text) and how context history is managed.

## Impact

- `kb_agent.agent.nodes.py`: `synthesize_node` and `tool_node` modifications.
- `kb_agent.engine.py`: Return type of `answer_query` will change.
- `kb_agent.tui.py`: Major changes to `_run_query`, history management, and the addition of a new `SourceDetailScreen` modal.
