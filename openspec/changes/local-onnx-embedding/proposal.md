## Why

In restricted or offline environments (like internal bank networks), the system cannot download the default `all-MiniLM-L6-v2` embedding model from the internet used by ChromaDB's default embedding function. Also, adding `sentence-transformers` and `torch` frameworks bloats the offline deployment. This change introduces support for loading a local ONNX-formatted model (specifically `bge-small-zh-v1.5`) via the lightweight `onnxruntime` already utilized by ChromaDB, enabling offline semantic search without heavy PyTorch dependencies. 

## What Changes

- Add `onnxruntime` dependency to `pyproject.toml` (if not already fully leveraged/exposed).
- Create a custom `ONNXEmbeddingFunction` in `kb_agent/tools/vector_tool.py` that loads local `.onnx` models.
- Introduce a new configuration `KB_AGENT_EMBEDDING_MODEL_PATH` in `config.py` and `.env.example`.
- Update the initialization logic in `VectorTool` to fallback: `embedding_url` (OpenAI/remote) -> `embedding_model_path` (Local ONNX) -> ChromaDB default.

## Capabilities

### New Capabilities
- `local-onnx-embedding`: Support for loading offline ONNX embedding models via `onnxruntime` for ChromaDB without heavy PyTorch dependencies.

### Modified Capabilities
- 

## Impact

- **Vector Tool (`kb_agent/tools/vector_tool.py`)**: Modified to support the new embedding function fallback logic.
- **Config (`kb_agent/config.py`)**: Added `embedding_model_path` variable and path resolution.
- **Dependencies (`pyproject.toml`)**: Added `onnxruntime` if necessary, keeping the environment lightweight.
- **Existing ChromaDB Indexes**: Users switching to a new embedding model (e.g., from 384-dim MiniLM to 512-dim BGE) will need to rebuild their existing `.chroma` databases as dimensions and vector spaces change.
