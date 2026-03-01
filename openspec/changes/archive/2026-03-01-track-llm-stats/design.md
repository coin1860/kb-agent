## Context

The current `kb-agent` RAG pipeline utilizes `langgraph` with multiple nodes invoking the LLM (Large Language Model) to execute the workflow (`analyze_and_route`, `plan`, `grade_evidence`, `synthesize`, etc.). However, these LLM calls are executed ad-hoc within each node without any centralized tracking mechanism for tracking how many tokens each query consumes or the number of API calls made.

By capturing these metrics natively in the `AgentState`, developers and users can visualize the operational cost of the query execution pipeline directly.

## Goals / Non-Goals

**Goals:**
- Provide runtime transparency into token consumption and LLM latency (measured in API calls).
- Modify `AgentState` to store global metrics across the graph.
- Implement a non-intrusive wrapper over the native `llm.invoke` calls to centralize tracking.
- Enhance the output message in the `synthesize_node` to display these metrics to the end user.

**Non-Goals:**
- Do not implement complex token cost (pricing) calculations based on different provider rates right now.
- Do not store these metrics persistently in a database; they are solely to be aggregated within runtime per query execution and piped back to the UI.

## Decisions

**1. Create an `_invoke_and_track` wrapper function**
Instead of polluting each node with identical status accumulation boilerplate, we'll implement a helper function in `kb_agent/agent/nodes.py` that intercepts the `llm.invoke` call. This helper wrapper will:
- Check if state has token counters installed, default them to `0` if not.
- Fire the `llm.invoke`.
- Read LangChain's `usage_metadata` or generic `response_metadata` provided by the model.
- Accumulate the extracted prompt, completion, and total tokens into `AgentState`. 
- Increment the counter for total calls made.

*Rationale*: This guarantees consistent behavior whenever an LLM is asked to output text.

**2. Modify `AgentState` schema**
Add tracking variables strictly to `kb_agent/agent/state.py`
```python
llm_call_count: int
llm_prompt_tokens: int
llm_completion_tokens: int
llm_total_tokens: int
```

**3. Format Stats in `synthesize_node`**
In `synthesize_node`, immediately after assembling the answer and citation footers, we inject the LLM Usage Stats dashboard as an additional formatted Markdown block. We also need to add tracking for the `synthesize_node` LLM invocation itself. Note that since this is the last step, it should append the metrics right before returning.

## Risks / Trade-offs

- **Risk: Not all model providers return consistent `usage_metadata` via LangChain.**
  - **Mitigation:** Fallback logic to look inside `response_metadata` for token variables. For OpenAI vs Groq endpoints, the payload may differ slightly, so we use `.get("prompt_tokens", 0)` to default gracefully.

- **Risk: Adding LLM calls in the UI may increase vertical space usage.**
  - **Mitigation:** We'll collapse it to a very concise 4-line summary or visually separate it with a horizontal rule so it doesn't distract from the core answer.
