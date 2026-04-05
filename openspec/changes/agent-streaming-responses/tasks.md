## 1. Planner Streaming Implementation

- [ ] 1.1 In `src/kb_agent/skill/planner.py`, refactor `decide_next_step` to use `llm.bind_tools(tools).stream(messages)`. Update it to return a generator that yields structured events (thought, tool_call, final_answer).
- [ ] 1.2 Implement a stream aggregator in `decide_next_step` to ensure that even while streaming, the final complete message is captured for history tracking.

## 2. Shell & Renderer Integration

- [ ] 2.1 In `src/kb_agent/skill/renderer.py`, add support for live-updating a "Thought" block. This may involve using `Rich.Live` or a similar mechanism to append chunks.
- [ ] 2.2 In `src/kb_agent/skill/shell.py`, update the `_execute_milestone` and `_legacy_execute_loop` to iterate over the stream from `decide_next_step`.
- [ ] 2.3 Ensure that tool execution only starts after the full tool call has been received from the stream.

## 3. Verification & Cleanup

- [ ] 3.1 Update unit tests in `tests/skill/test_decide_next_step.py` to handle the new generator return type.
- [ ] 3.2 Perform an end-to-end manual test to verify the streaming experience in the terminal.
