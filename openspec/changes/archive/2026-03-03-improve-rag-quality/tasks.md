## 1. Synthesize Prompt Overhaul (P0)

- [x] 1.1 Update `SYNTHESIZE_SYSTEM` in `nodes.py`: replace "Be precise, professional, and well-structured" with "Be thorough and detailed" directive; add instructions to extract ALL details and prefer long answers
- [x] 1.2 Run existing tests: `pytest tests/agent/test_grade_evidence.py tests/test_engine_mock.py -v`

## 2. Tool Error Filtering (P0)

- [x] 2.1 Add error detection logic in `tool_node` (`nodes.py`): check for `metadata.error == True` in parsed JSON results and `status: "error"` in dict results; skip adding to context, log with `error: True` in tool_history
- [x] 2.2 Update `vector_search` in `tools.py` to return `{"status": "no_results", ...}` instead of `[]` when results are empty
- [x] 2.3 Update `graph_related` in `tools.py` to return `{"status": "no_results", ...}` instead of `[]` when no related entities found
- [x] 2.4 Run existing tests: `pytest tests/agent/ -v`

## 3. Fix doc_id Naming Bug (P1)

- [x] 3.1 Change `LocalFileConnector.fetch_all` and `fetch_data` in `connectors/local_file.py`: use `file_path.stem` instead of `file_path.name` for the `id` field
- [x] 3.2 Verify `Processor.process` in `processor.py` produces `.md` files with clean names (stem-based)
- [x] 3.3 Run existing tests: `pytest tests/test_local_file.py -v`

## 4. Rule-based First-Round Routing (P1)

- [x] 4.1 Modify `plan_node` in `nodes.py`: when `iteration == 0` and no `existing_context`, skip LLM planner and apply rule-based tool selection (URL → web_fetch, JIRA key → jira_fetch, default → vector_search)
- [x] 4.2 Keep existing LLM planner logic for `iteration >= 1` (retry rounds)
- [x] 4.3 Run existing tests: `pytest tests/agent/test_plan_layer.py tests/agent/test_e2e_plan_node.py -v`

## 5. read_file Line-Range Support (P2)

- [x] 5.1 Add `start_line: int = None, end_line: int = None` parameters to `read_file` tool in `tools.py`
- [x] 5.2 Update `FileTool.read_file` in `file_tool.py` to support line range: read file, split by lines, return specified range with clamping
- [x] 5.3 Update `read_file` tool description in `TOOL_DESCRIPTIONS` in `nodes.py`

## 6. Automatic Context Expansion on REFINE (P2)

- [x] 6.1 In `plan_node` (`nodes.py`), when `grader_action == "REFINE"`: extract file paths from context using `_extract_file_paths_from_context`, issue `read_file` calls for up to 3 unread files before falling back to LLM planner
- [x] 6.2 Run tests: `pytest tests/agent/ -v`

## 7. Deprecate local_file_qa (P3)

- [x] 7.1 Remove `local_file_qa` from `ALL_TOOLS` list in `tools.py`
- [x] 7.2 Remove `local_file_qa` from `TOOL_DESCRIPTIONS` in `nodes.py`
- [x] 7.3 Remove `local_file_qa` from `_extract_tools_from_text` valid_tools list in `nodes.py`
- [x] 7.4 Run full test suite: `pytest tests/ -v`
