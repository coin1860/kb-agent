## 1. Engine Modifications

- [x] 1.1 Locate `_handle_urls` method in `src/kb_agent/engine.py`.
- [x] 1.2 Remove the conditional block `if mode == "knowledge_base":` which calls the Processor to process the fetched document.
- [x] 1.3 Verify that URL content is still being appended to `all_content` for temporary answer generation.

## 2. Verification

- [x] 2.1 Test by pasting a new URL in KB RAG mode in the TUI.
- [x] 2.2 Verify that the answer is generated based on the URL.
- [x] 2.3 Verify that NO new files are created in the `docs/` or `index/` directories (unless `/index` is used).
