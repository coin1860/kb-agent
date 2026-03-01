## Why

The current RAG agent routing flow is overly complex and fragile. The `analyze_and_route` node attempts to perform intent classification, query decomposition, and keyword extraction in a single LLM call. This frequently leads to JSON parsing failures and inaccurate keyword extraction. Consequently, the `hybrid_search` tool often receives entire sentences as its `exact_keywords` argument resulting in zero matches from Ripgrep, effectively downgrading the system to rely solely on Vector Search. Furthermore, the RRF (Reciprocal Rank Fusion) logic in `hybrid_search` uses file paths for deduplication, causing correct vector search chunks to be discarded if an earlier irrelevant keyword match occurs in the same file. Simplifying this flow by leaning on the LLM's inherent ability to issue parallel tool calls (e.g., calling both `grep_search` and `vector_search` independently) will dramatically improve robustness and retrieval quality while maintaining the goal of approximately 85% accuracy.

## What Changes

-   **Remove `analyze_and_route` node**: Remove the dedicated analysis node and its complex JSON output requirements.
-   **Consolidate planning logic in `plan_node`**: The `plan_node` will take over tool selection. For complex queries involving both exact matches and concepts, it will be instructed to issue parallel tool calls to both `grep_search` (with simplified keywords) and `vector_search`.
-   **Simplify or remove `hybrid_search`**: Since `plan_node` can orchestrate parallel searches, the dedicated `hybrid_search` tool wrapper and its buggy RRF deduplication logic will be removed.
-   **Simplify `AgentState`**: Remove fields associated with the old analysis node, such as `sub_questions` and `routing_plan`.
-   **Streamline Graph Topology**: The graph will transition from a 6-node adaptive structure to a more direct `START -> plan_node -> tool_exec -> grade_evidence -> synthesize -> END` flow. The `grade_evidence` node will handle the aggregation and filtering of results from the parallel tool calls.

## Capabilities

### New Capabilities
- `parallel-retrieval`: Orchestrated execution of multiple search tools (e.g., grep and vector) in parallel from the planning node to gather comprehensive evidence without relying on a monolithic hybrid search function.

### Modified Capabilities
- `query-routing`: Transitioning from explicit structured pre-analysis to streamlined, in-planning tool selection based on intent.

## Impact

-   **`src/kb_agent/agent/graph.py`**: Topology changes to remove `analyze_and_route`.
-   **`src/kb_agent/agent/nodes.py`**: Deletion of `analyze_and_route_node`, simplification of `AgentState`, and update of `plan_node` prompts to encourage parallel tool usage.
-   **`src/kb_agent/agent/state.py`**: Simplification of the state dictionary.
-   **`src/kb_agent/agent/tools.py`**: Removal or deprecation of the `hybrid_search` tool.
-   **Reduction in LLM Calls/Tokens**: Skipping the initial analysis node reduces latency and token consumption per query.
