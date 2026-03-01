## 1. Core Logic

- [x] 1.1 Update `tool_node` in `src/kb_agent/agent/nodes.py` to parse JSON and include file/chunk counts in status messages.
- [x] 1.2 Update citation formatting in `tool_node` (`src/kb_agent/agent/nodes.py`) to prioritize `metadata["path"]`.

## 2. Verification

- [x] 2.1 Verify `grep_search` log shows "(X files matched)".
- [x] 2.2 Verify `vector_search` log shows "(X chunks found)".
- [x] 2.3 Verify sources list contains actual file paths instead of "local_file".
