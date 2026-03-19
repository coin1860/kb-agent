## Context

The current `kb-agent` RAG pipeline executes retrieved chunks by grouping decomposed vectors from ChromaDB and truncating them down to a small `top-k` set for context synthesis. This direct truncation ignores nuanced relationships across multiple retrieved context paths. We want to implement a secondary reranking step using `bge-reranker-v2-m3-Q4_K_M.gguf`. To maintain low setup complexity, we opt to use standard `llama-cpp-python` rather than a separate child process for the llama HTTP server.

## Goals / Non-Goals

**Goals:**
- Add a new LangGraph node (`rerank_node`) that intercepts merged contexts before synthesis.
- Conditionally invoke a cross-encoder model via `llama-cpp-python` if a new TUI setting `use_reranker` is enabled.
- Allow async model loading upon start-up or setting activation so as not to freeze the TUI.
- Scale intermediate vector search limits to return ~20 chunks before pruning to the best 3.

**Non-Goals:**
- Creating an external proxy API for reranking.
- Embedding generation modifications.

## Decisions

1. **Reranker Node placement**: We place `rerank_node` immediately after `tool_node` and before `synthesize_node` (and `evaluate_node`). This isolates sorting logic from LLM synthesis and makes it easy to bypass if `use_reranker=False`.
2. **Execution Engine**: We directly use `llama-cpp-python` via its python bindings rather than spinning up `llama-server`. This keeps the application as a single process and requires only a `pip install` to setup.
3. **Async Model Loading**: Because initializing the GGUF model can consume 5-10 seconds of processing time, we initialize `Llama(model_path=..., ...)` asynchronously using Python `threading.Thread` or `asyncio.to_thread`.
4. **Candidate Selection Size**: If reranking is enabled, `vector_tool` will fetch up to 7 chunks per sub-query (`n=7`), resulting in ~20 chunks after distinct operations. The reranker scores them all and returns the absolute top 3 for synthesis. If disabled, the legacy truncate to top-4 continues.

## Risks / Trade-offs

- **[Risk]** Heavy memory usage per application run due to simultaneous LLM, ONNX Embedding, and GGUF Reranker instances.
  - *Mitigation*: The feature defaults to disabled. Memory can also be controlled using thread limits on `llama-cpp-python`.
- **[Risk]** TUI blockage.
  - *Mitigation*: The Llama.cpp backend is strictly instantiated in a non-blocking background thread. Repeated queries wait gracefully.
