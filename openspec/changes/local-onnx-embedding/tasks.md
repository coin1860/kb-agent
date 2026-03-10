## 1. Project Configuration

- [x] 1.1 Update `pyproject.toml` to include `onnxruntime` and `tokenizers` dependencies
- [x] 1.2 Add `embedding_model_path` to `Settings` in `src/kb_agent/config.py`
- [x] 1.3 Add `KB_AGENT_EMBEDDING_MODEL_PATH` example to `.env.example`

## 2. Core Implementation

- [x] 2.1 Create custom `ONNXEmbeddingFunction` class in `src/kb_agent/tools/vector_tool.py` that loads the local ONNX model and tokenizer
- [x] 2.2 Update `VectorTool.__init__` to check for `embedding_model_path` configuration
- [x] 2.3 Implement fallback logic: URL -> Local ONNX -> Default
- [x] 2.4 Set the absolute default model path to `./models/bge-small-zh-v1.5` if no URL and no explicit path is given
- [x] 2.5 Add `embedding_model_path` field to the TUI `/settings` command
- [x] 2.6 Update logic: Path becomes `embedding_model_path / embedding_model`, defaulting to `./models/ / embedding_model` if path is empty

## 3. Verification

- [x] 3.1 Write tests or verify end-to-end functionality using a sample offline ONNX model
