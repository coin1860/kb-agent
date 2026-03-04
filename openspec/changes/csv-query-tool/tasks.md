## 1. Tool Implementation

- [x] 1.1 Create `src/kb_agent/tools/csv_qa_tool.py` with standard tool interface
- [x] 1.2 Implement `_df_cache` dictionary and `clear_cache()` method
- [x] 1.3 Implement file loading logic to search `data/archive/` then `data/source/`
- [x] 1.4 Implement safe Pandas query execution logic parsing `condition` and `columns` from LLM JSON output
- [x] 1.5 Add error handling block to return execution errors to the LLM for self-correction

## 2. Agent Router Updates

- [x] 2.1 Update `kb_agent/agent/nodes.py` system prompts (in `analyze_and_route`) to identify `.csv` queries
- [x] 2.2 Add instruction to output `"direct"` action to `csv_query` tool instead of vector search
- [x] 2.3 Ensure the `csv_query` tool is properly registered and accessible in the agent's tool registry

## 3. Cache Lifecycle Management

- [x] 3.1 Update `kb_agent/tui.py` `action_clear_chat` to import and call `csv_qa_tool.clear_cache()` to release memory
