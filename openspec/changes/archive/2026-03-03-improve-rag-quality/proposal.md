## Why

The agent RAG system has poor retrieval quality: the LLM frequently picks the wrong tool on the first attempt (especially `local_file_qa`), returns sparse summaries despite having thousands of chars of evidence, and silently passes error responses (HTTP failures, connection errors) into the context where the LLM treats them as knowledge. Additionally, the indexing pipeline has a file naming bug where `source/a.docx` produces `index/a.docx.md` instead of `index/a.md`.

## What Changes

- **Synthesize prompt overhaul**: Replace "Be precise" with "Be thorough" directive to produce comprehensive answers instead of overly-brief summaries
- **Tool error filtering**: Detect connector error responses (Jira/Confluence/Web) and prevent them from entering the evidence context; add explicit "no results" feedback for empty search results
- **Default vector_search-first strategy**: Make `plan_node` always use `vector_search` on the first round via rules, deferring LLM-based tool selection to retry rounds only
- **`read_file` line-range support**: Add optional `start_line`/`end_line` parameters to `read_file` so the system can retrieve ±100 lines around a matched chunk rather than the entire file
- **Automatic read_file follow-up**: When grader returns REFINE, automatically extract file paths from vector_search results and issue `read_file` calls to fetch surrounding context
- **Fix `doc_id` naming**: Change file naming from `{filename}.md` to `{stem}.md` so `report.docx` generates `index/report.md` not `index/report.docx.md`
- **Deprecate `local_file_qa`**: Remove from `ALL_TOOLS` to prevent LLM misuse; its file-listing behavior can be achieved via vector_search + metadata extraction

## Capabilities

### New Capabilities

- `retrieval-context-expand`: Automatic context expansion via `read_file` when vector_search chunks are insufficient. Includes line-range parameter support and auto-follow-up on REFINE.
- `tool-error-handling`: Unified error detection and filtering for all tool/connector results, preventing error messages from contaminating the evidence context.

### Modified Capabilities

- `synthesis-rag-pipeline`: Update synthesize prompt to produce thorough, detailed answers instead of terse summaries
- `retrieval-hybrid`: Add line-range support to `read_file` tool; update `vector_search` to return explicit "no results" feedback
- `ingestion-indexing-pipeline`: Fix `doc_id` derivation to use `Path.stem` instead of `Path.name`, producing correct `.md` filenames
- `routing-adaptive`: Replace LLM-based first-round tool selection with rule-based `vector_search` default; LLM planner only for retry rounds
- `synthesis-local-qa`: Deprecate — remove `local_file_qa` from `ALL_TOOLS` to reduce tool confusion

## Impact

- **Files modified**: `nodes.py` (plan_node, tool_node, synthesize_node), `tools.py` (tool wrappers + ALL_TOOLS), `processor.py` (doc_id fix), `local_file.py` (doc_id fix), `file_tool.py` (line-range support)
- **Re-indexing required**: After `doc_id` fix, users must re-run `kb-agent index` to rebuild ChromaDB with correct file paths
- **Tests affected**: `test_plan_layer.py`, `test_grade_evidence.py`, `test_local_file_qa.py`, `test_local_file.py`
- **No breaking API changes**: All changes are internal to the agent pipeline
