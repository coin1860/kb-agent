## Why

The agent currently plans tool execution without looking at the conversation history, which causes the agent to lose context of entities mentioned in prior messages (e.g. Jira tickets like FSR-123) and execute unnecessary, generic searches for conversational follow-up prompts. A dedicated routing node that analyzes the full history and extracts active entities would enable the agent to maintain context across a multi-turn conversation, support coreferences, and execute tool sequences more intelligently.

## What Changes

- Introduce a new `analyze_and_route` node at the start of the LangGraph pipeline, acting as a "global brain" that receives the full conversation history.
- Implement conditional routing out of `analyze_and_route` to either handle a query directly (`synthesize` for chit-chat, translations, summarizing past answers) or send it to the retrieval tools (`plan` for searching).
- Equip the `analyze_and_route` node with query rewriting to resolve pronouns or vague references using the context of past answers, and entity extraction to identify active entities.
- Simplify `plan_node` so that it focuses purely on selecting retrieval tools based on the pre-resolved queries and explicitly provided active entities.
- Update the shared LangGraph `AgentState` schema to track routing decisions, the resolved query, and active entities across node boundaries.

## Capabilities

### New Capabilities
- `stateful-routing`: The agent now maintains context of active entities from prior turns and determines the necessity of tool usage vs direct answering on a per-query basis.

### Modified Capabilities
- `multi-turn-memory`: Expands conversational memory context to actively inform retrieval planning, not just final synthesis.

## Impact

- `agent/graph.py`: The top-level workflow topology will be updated to point `START` at `analyze_and_route`. Conditional edges will be added to handle skipping the retrieval phase.
- `agent/state.py`: The `AgentState` schema will be expanded to include routing flags (`route_decision`), contextually resolved questions (`resolved_query`), and contextual clues (`active_entities`).
- `agent/nodes.py`: A new `analyze_and_route` function and prompt will be added. The `plan_node` logic will be simplified by removing URL fast-paths and moving intention analysis upstream. `synthesize_node` chit-chat detection will be replaced by the routing node's decision.
