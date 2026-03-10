## 1. Update Agent State

- [x] 1.1 Add `route_decision`, `resolved_query` (str), and `active_entities` (list[str]) to the `AgentState` schema in `agent/state.py`.

## 2. Implement Routing Node

- [x] 2.1 Create the structured LLM system prompt for the new router (e.g. `ANALYZE_AND_ROUTE_SYSTEM`) to decide between direct answers and search.
- [x] 2.2 Implement the `analyze_and_route_node` function in `agent/nodes.py` taking in the conversation history and the state query.
- [x] 2.3 Have `analyze_and_route_node` parse the output to construct the `route_decision`, `resolved_query`, and `active_entities` and return them via state updates.

## 3. Refactor Execution Nodes

- [x] 3.1 Modify `plan_node` in `agent/nodes.py` to utilize `state['resolved_query']` rather than raw `state['query']` for searching/LLM planning.
- [x] 3.2 Add `active_entities` passing to the `plan_node` context to serve as firm contextual hints for retrieving Jira/Confluence.
- [x] 3.3 Strip out legacy URL fast-path matching out of `plan_node` and handle it neatly under the routing hierarchy (or keep it if it serves as a fail-safe, but streamline it).

## 4. Rebuild Graph Topology

- [x] 4.1 Update `agent/graph.py` to add `analyze_and_route` as a node.
- [x] 4.2 Set entry point to `analyze_and_route` instead of `plan`.
- [x] 4.3 Add a conditional edge from `analyze_and_route`: route to `synthesize` if `route_decision == "direct"`, or route to `plan` if `route_decision == "search"`.
