## Why

Currently, the knowledge base agent makes multiple LLM calls across its RAG pipeline (e.g., query analysis, planning, grading, and synthesis). However, there is no centralized tracking of how many calls are made or how many tokens are consumed. Tracking LLM API calls and token usage is critical to evaluating the cost, performance, and optimization surface of the system, especially when users evaluate complex queries in a production environment.

## What Changes

- Wrap LLM invocation calls across all LangGraph nodes to intercept and accumulate usage metadata tracking (call count, prompt tokens, completion tokens, total tokens).
- Store these execution metrics centrally within the `AgentState`.
- Modify the final `synthesize_node` action to append a formatted summary block (e.g., "📊 LLM Usage Stats") containing total token usage and API call count at the end of the generator's response.

## Capabilities

### New Capabilities
- `llm-usage-tracking`: Track the global state of LLM usage (call count, tokens) across all steps of the agent workflow.

### Modified Capabilities
- `query-engine`: The response synthesis formatting is updated to include the generated LLM usage stats at the bottom of the answer output.

## Impact

- **Agent State (`AgentState`)**: Gets new fields to aggregate usage data.
- **Node Helpers (`nodes.py`)**: Needs a wrapper function over `llm.invoke()` to collect these stats without polluting the business logic of each node heavily.
- **Output Experience**: Users will now see an additional usage statistics block implicitly integrated into all successful retrieval answers.
