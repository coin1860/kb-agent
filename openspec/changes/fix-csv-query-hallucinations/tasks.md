## 1. Schema Tool Exposure

- [x] 1.1 In `kb_agent/agent/tools.py`, create a `csv_info` tool that wraps `get_csv_schema_and_sample` from `csv_qa_tool`.
- [x] 1.2 Add `csv_info` to the `ALL_TOOLS` list in `kb_agent/agent/tools.py` so the Agent can access it.
- [x] 1.3 Update the `csv_query` tool docstring prompt in `kb_agent/agent/tools.py` with a `CRITICAL INSTRUCTION` to force calling `csv_info` before performing any queries.

## 2. Error Handling & Self-Correction

- [x] 2.1 In `kb_agent/tools/csv_qa_tool.py`, update the `csv_query` function's `try...except` block for Pandas string condition evaluation.
- [x] 2.2 When an exception is caught in `csv_query` (e.g., column not found), generate a detailed error message containing `list(df.columns)` and strict instructions avoiding the same erroneous query to enable LangGraph's auto-correction.
