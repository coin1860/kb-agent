## Context

The `kb-agent` relies on embeddings for semantic search over indexed documents. The existing system supports using an external OpenAI-compatible API via `KB_AGENT_EMBEDDING_URL`. When this is not configured, ChromaDB falls back to downloading its default sentence-transformer model (`all-MiniLM-L6-v2`) from the internet. In highly restricted offline environments, such as internal bank networks, both internet access and large dependency footprints (like `torch` and `sentence-transformers`) are strictly prohibited or undesirable.

## Goals / Non-Goals

**Goals:**
- Enable the use of local, pre-downloaded ONNX embedding models (such as `bge-small-zh-v1.5`) for offline semantic search.
- Integrate the local model capability directly into ChromaDB without introducing heavy machine learning frameworks like PyTorch or `sentence-transformers`.
- Keep the system easy to configure using environment variables.

**Non-Goals:**
- Auto-conversion of PyTorch models (`.safetensors`, `.bin`) to ONNX at runtime. Users must provide a pre-converted ONNX model.
- Providing support for local LLM inference in this specific change.

## Decisions

### 1. Using ONNXRuntime vs. PyTorch (SentenceTransformers)
**Decision**: We will implement a custom `ONNXEmbeddingFunction` utilizing `onnxruntime` and `tokenizers`.
**Rationale**: ChromaDB already depends on `onnxruntime` for its default behavior. Adding `sentence-transformers` requires adding `torch`, which introduces hundreds of megabytes of dependencies, complicating offline deployment and security scanning. By using `onnxruntime`, we keep the agent lightweight.

### 2. Configuration Strategy
**Decision**: Introduce `KB_AGENT_EMBEDDING_MODEL_PATH` in `config.py`.
**Rationale**: This clearly separates remote API usage (`KB_AGENT_EMBEDDING_URL`) from local offline usage. The initialization logic in `kb_agent/tools/vector_tool.py` will prioritize:
1. Remote API (`KB_AGENT_EMBEDDING_URL`)
2. Local ONNX Model (`KB_AGENT_EMBEDDING_MODEL_PATH`)
3. Default ChromaDB Model (Fallback)

### 3. Dependency Management
**Decision**: Explicitly add `onnxruntime` and `tokenizers` to `pyproject.toml` dependencies if they are not already installed or sufficiently exposed by ChromaDB.
**Rationale**: A local ONNX embedding function needs a tokenizer to process text before passing it to the ONNX model. The `tokenizers` package is lightweight and standard for this.

## Risks / Trade-offs

- **Risk: Model Compatibility**: Not all ONNX models and tokenizers behave exactly the same way. The custom embedding function will need to handle standard BERT-like sequence outputs.
  - *Mitigation*: The implementation will be tailored for standard BERT architectures (like BGE), applying mean pooling and normalization.
- **Risk: Index Rebuilds**: Switching from the default MiniLM (384-dim) to BGE (512-dim) alters the embedding space.
  - *Mitigation*: This is an operational concern. Existing users will simply need to clear their `.chroma` directory and re-index their documents when changing the underlying model.
