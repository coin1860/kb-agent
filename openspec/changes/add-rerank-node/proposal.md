## Why

The current retrieval pipeline decomposes a user query into up to 3 sub-queries and executes vector search concurrently to aggregate chunks. However, passing all retrieved chunks to the LLM can dilute relevance and increase token usage, while limiting the initial retrieval might miss critical context. Adding a dedicated rerank stage lets the system fetch a larger candidate pool (~20 distinct chunks) and use a cross-encoder model to accurately score and filter down to the top 3 highly relevant chunks before synthesis.

## What Changes

- Introduce a new LangGraph node (`rerank_node`) placed after the `tool_node` and before `synthesize_node` / `evaluate_node`.
- Modify `vector_tool.search()` to optionally fetch more chunks (e.g., `n=7`) per query to broaden the initial candidate pool.
- Introduce `llama-cpp-python` (via `pip`) to load a local GGUF reranker model (like `bge-reranker-v2-m3-Q4_K_M.gguf`) in the same process.
- Load the reranker model asynchronously when the application starts or the setting is toggled on, preventing the TUI from freezing.
- Add a new `use_reranker` toggle in the TUI Settings; default is disabled. Modifying this setting will prompt the user to restart the application.
- Retain the existing fallback logic (truncate to top 4) if the reranker is disabled.

## Capabilities

### New Capabilities
- `retrieval-reranking`: A capability specifying cross-encoder reranking to accurately prioritize top context chunks before LLM synthesis.

### Modified Capabilities
- `tui-settings`: Addition of a Reranker toggle and configuration, with a restart prompt.
- `retrieval-query-decompose`: Changes to the number of results retrieved per sub-query to support a larger candidate pool for reranking.

## Impact

- **Engine DAG**: `agent/graph.py` and `agent/nodes.py` state flow will route through `rerank_node`.
- **Dependencies**: Adds `llama-cpp-python` to project requirements.
- **Resource Usage**: Slight memory increase (model weight) and CPU inference load when reranking is enabled; cleanly bypassed when disabled.
