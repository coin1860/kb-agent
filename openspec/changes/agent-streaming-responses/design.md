## Context

The KB-CLI agent's `decide_next_step` now uses native tool calling, but it waits for the full LLM response before continuing. This causes a pause in the terminal UI that can be confusing for the user. We want to stream the LLM's output so that the user can see the agent "thinking" in real-time.

## Goals / Non-Goals

**Goals:**
- Update `decide_next_step` to return a generator (or use a callback) that streams LLM chunks.
- Update `SkillShell` to consume this stream and update the UI incrementally.
- Ensure tool call extraction still works reliably with partial chunks or after the stream completes.
- Support streaming for both "thought" (content) and "act" (tool calls).

**Non-Goals:**
- Changing the underlying LLM provider or tool binding logic.
- Implementing UI changes beyond the terminal (e.g., web UI).
- Parallel tool execution (still deferred).

## Decisions

- **Streaming Interface**: `decide_next_step` will be refactored to use `llm.bind_tools(tools).stream(messages)`. It will yield a sequence of events: `{"type": "thought", "text": "..."}`, `{"type": "tool_call", "tool": "...", "args": {...}}`, or `{"type": "final_answer", "text": "..."}`.
- **Incremental Rendering**: The `SkillRenderer` will be updated to handle partial text updates for the "Think" block. We will use `Rich.Live` or incremental print logic to update the current block without flickering.
- **Sync/Async Handling**: Since the current `SkillShell` is synchronous, we will use synchronous streaming first. If performance requires it, we may consider `astream`, but synchronous `.stream()` is simpler for the initial implementation.
- **State Preservation**: The `tool_history` update will still occur after a tool call is FULLY received and executed, maintaining the existing logic for task state.

## Risks / Trade-offs

- [Risk] **UI Flickering**: Rapidly updating the terminal can cause flickering.
  → Mitigation: Use `Rich.Live` or debounce updates to ensure a smooth visual experience.
- [Risk] **Partial Tool Call Parsing**: Extracting tool calls from a stream can be tricky if the chunk boundaries are weird.
  → Mitigation: We will wait for the `tool_calls` field in the message to be fully populated by the stream aggregator (or use LangChain's built-in stream tool-call handling).
