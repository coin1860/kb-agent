## 1. Setup and Configurations

- [x] 1.1 Add `llama-cpp-python` to project dependencies
- [x] 1.2 Update `config.py` to include `use_reranker` (bool, default False) and `reranker_model_path` (default to `./models/bge-reranker-v2-m3-Q4_K_M.gguf` under the `models/` directory)

## 2. TUI Settings Updates

- [x] 2.1 Update `kb_agent.tui` (Settings component) to include a switch for Reranker and a text input for the reranker model path
- [x] 2.2 Add an inline notification/toast in the TUI indicating that enabling the Reranker requires a restart to load the model

## 3. Reranker Logic and Async Initialization

- [x] 3.1 Create `kb_agent/tools/reranker.py` with a `RerankClient` that wraps the `llama_cpp.Llama` model and handles async initialization via `asyncio.create_task` to prevent blocking the startup thread
- [x] 3.2 Add a `rerank(query, chunks, top_n)` method to score items where `query` and `chunk` are concatenated and tokenized correctly
- [x] 3.3 Ensure the client is instantiated and begins loading the model upon application start (if enabled) logits score

## 4. LangGraph and Sub-query Adjustments

- [x] 4.1 In `agent/nodes.py`, update `vector_search` query parameter dynamically: fetch `n=20` if `use_reranker` is true, otherwise keep `n=5`
- [x] 4.2 Create `rerank_node` function in `agent/nodes.py` that intercepts the `context` coming from `tool_node`
- [x] 4.3 In `rerank_node`, if `use_reranker` is true, evaluate chunks through `RerankClient.rerank_sync()`. If false, bypass filtering.
- [x] 4.4 Update `agent/graph.py` to add `rerank_node` to the DAG, replacing edges from `tool_node` to `evaluate_node`/`synthesize_node` with edges traversing `rerank_node` first
