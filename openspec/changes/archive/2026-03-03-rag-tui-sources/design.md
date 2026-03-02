## Context

The current `kb-agent` aggregates search results (documents, Jira tickets, etc.) into context strings formatted as `[SOURCE:path:L#] content`. The `synthesize_node` uses this context to generate a final answer, appending a plain-text `Sources:` footer at the end. 

This approach has two major flaws:
1. **Loss of Metadata**: Vector search scores are dropped in the `tool_node` when concatenating contexts.
2. **Context Poisoning**: Because the `Sources:` footer is baked into the LLM's `AIMessage` output, it gets stored in the `chat_history`. During multi-turn chats, the LLM reads its previous sources as part of the conversational context, often leading to hallucinations where it verbatim repeats old sources for new questions (the "echochamber" effect).

## Goals / Non-Goals

**Goals:**
- Decouple source metadata from the LLM textual generation entirely.
- Pass rich source metadata (filename, chunk content, similarity percent) to the UI layer.
- Render clickable source links in the Textual TUI that open a modal with the source content.
- Ensure the LLM's multi-turn conversational history is 100% clean of source metadata to prevent hallucinations.

**Non-Goals:**
- Changing the underlying retrieval logic (ChromaDB, Jira, Web).
- Changing the CRAG grading logic.

## Decisions

### 1. Separation of Answer and Sources (Option A)
We will refactor `synthesize_node` (in `kb_agent/agent/nodes.py`) so that the final state dictionary contains two distinct fields:
- `final_answer`: The pure textual response from the LLM.
- `sources`: A structured list of dicts: `[{"path": "...", "score": 0.95, "content": "..."}]`.
**Rationale**: By keeping them separate, the `Engine` and the `TUI` can handle the rendering independently. It completely eliminates the need for regex stripping of the `Sources:` footer from the history, because the `final_answer` will never contain it in the first place.

### 2. TUI Clickable Action Links
In Textual, `RichLog` does not allow embedding full interactive widgets (like `Collapsible`). Instead, we will use Textual's markup action links: `[@click=show_source(index)]...[/]`.
**Rationale**: This enables clickable inline elements inside the streaming/log content. Clicking the link will trigger an action on the parent `App` or `Screen`, which will then push a new `ModalScreen` to display the source text.

### 3. Source Metadata Preservation
The `tool_node` needs to preserve vector search scores. When `vector_search` returns JSON with scores, `tool_node` will embed the score into the context string: `[SOURCE:/path:L1:S0.15]`.
**Rationale**: `synthesize_node` needs to parse the context items to build the structured `sources` list. Embedding the score in the tag ensures it survives the CRAG grading and filtering pipeline untouched until synthesis.

## Risks / Trade-offs

- **Risk**: Other tools (Jira, Web, Grep) do not have "scores" in the same way vector search does.
  - **Mitigation**: The `[SOURCE:...:S...]` format will treat the score as optional. If absent, the TUI will not display a percentage.
- **Risk**: Changing the return signature of `Engine.answer_query` might break unit tests.
  - **Mitigation**: We will update `answer_query` to return both `answer` and `sources` (e.g., as a tuple or dict), and update the corresponding assertions in `tests/`.
