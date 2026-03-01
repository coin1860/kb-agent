## 1. Schema Updates

- [x] 1.1 Add tracking fields (`llm_call_count`, `llm_prompt_tokens`, `llm_completion_tokens`, `llm_total_tokens`) to `AgentState` schema in `kb_agent/agent/state.py`.

## 2. LLM Invocation Wrapper

- [x] 2.1 Implement `_invoke_and_track(llm: ChatOpenAI, messages: list, state: AgentState) -> AIMessage` helper function in `kb_agent/agent/nodes.py`.
- [x] 2.2 In `_invoke_and_track`, safely query `response.usage_metadata` or `response.response_metadata` for tokens, and accumulate them into the tracking fields in `AgentState`.
- [x] 2.3 Increment the `llm_call_count` by 1 within `_invoke_and_track` upon a successful LLM call.

## 3. Node Integration

- [x] 3.1 Replace direct `llm.invoke` calls with `_invoke_and_track(llm, messages, state)` inside `analyze_and_route_node`.
- [x] 3.2 Replace direct `llm.invoke` calls with `_invoke_and_track(llm, messages, state)` inside `plan_node`.
- [x] 3.3 Replace direct `llm.invoke` calls with `_invoke_and_track(llm, messages, state)` inside `grade_evidence_node`.
- [x] 3.4 Replace direct `llm.invoke` calls with `_invoke_and_track(llm, messages, state)` inside `synthesize_node` (for both normal flow and the chitchat fallback flow).

## 4. UI Rendering

- [x] 4.1 Update `synthesize_node` to append the LLM Usage Stats block (`📊 **LLM Usage Stats:**`...) to the returned `final_answer`.
- [x] 4.2 Validate the rendering triggers correctly even when context items are filtered/missing.
