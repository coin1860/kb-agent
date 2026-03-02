## Context

The agent RAG system suffers from three interconnected quality issues:

1. **Retrieval**: The LLM planner often selects wrong tools on the first attempt. `local_file_qa` (a thin `vector_search` wrapper returning only filenames) confuses the LLM. The `analyze_and_route` node was previously removed because it misclassified complex queries as chitchat.
2. **Error contamination**: Tool connectors (Jira, Confluence, Web) return HTTP errors as normal data `[{content: "Failed to fetch: ConnectionError..."}]`. These flow into evidence context and the LLM synthesizes them as if they were real knowledge.
3. **Sparse synthesis**: The synthsize prompt ("Be precise") combined with `temperature=0.2` produces minimal answers even when thousands of chars of evidence are available.
4. **File naming bug**: `LocalFileConnector` uses `file_path.name` as `doc_id` (e.g., `report.docx`), causing Processor to create `index/report.docx.md` instead of the expected `index/report.md`.

## Goals / Non-Goals

**Goals:**
- Improve first-query hit rate by defaulting to `vector_search` without LLM planner overhead
- Prevent error messages from contaminating evidence context
- Produce thorough, detailed answers from available evidence  
- Fix file naming to produce clean `.md` files in the index
- Add context expansion via line-range `read_file` for post-search enrichment
- Reduce tool confusion by deprecating redundant `local_file_qa`

**Non-Goals:**
- Re-implementing `analyze_and_route` node (it was removed for causing misclassification; we use rules instead)
- Changing the LangGraph topology or adding new graph nodes
- Modifying ChromaDB embedding or chunking strategy
- Adding new external tool integrations

## Decisions

### Decision 1: Rule-based first-round routing instead of LLM planner

**Choice**: On the first iteration (`iteration == 0`), `plan_node` bypasses LLM call entirely and applies simple rules:
- Contains URL → `web_fetch`
- Contains JIRA key pattern → `jira_fetch`  
- Default → `vector_search` with original query

**Why not LLM-based routing**: The previous `analyze_and_route` node was removed because smaller/local LLMs frequently misclassified complex queries. Rule-based routing is deterministic, zero-latency, and correct for the common case.

**LLM planner still used**: On retry rounds (iteration ≥ 1), the LLM planner selects tools as before, with awareness of what's already been tried.

### Decision 2: Error detection via metadata `error` flag

**Choice**: All connectors already set `metadata.error = True` on failure. We add detection in `tool_node` to check this flag and exclude error results from context. Error results are still logged in `tool_history` (with an `error: True` marker) so the planner knows what failed.

**Alternative considered**: Raising exceptions from connectors. Rejected because it would break the existing `tool_node` exception handling pattern and require broader changes.

### Decision 3: Prompt wording change for synthesis

**Choice**: Replace "Be precise, professional, and well-structured" with "Be thorough and detailed. Extract ALL relevant details from the evidence. Long, well-structured answers are PREFERRED over short ones."

**Why this works**: LLMs interpret "precise" as "brief". The word "thorough" + explicit instruction to prefer longer answers shifts behavior significantly. No code change needed beyond the prompt string.

### Decision 4: `doc_id` uses `Path.stem` 

**Choice**: Change `LocalFileConnector` to use `file_path.stem` instead of `file_path.name` as the document ID. This means `report.docx` → `doc_id = "report"` → `index/report.md`.

**Migration**: Requires re-indexing. Old `.docx.md` files in index directory should be manually cleaned or a cleanup step added to CLI.

### Decision 5: Line-range `read_file` with auto-follow-up

**Choice**: Add optional `start_line` and `end_line` parameters to `read_file`. On REFINE action, `plan_node` automatically extracts file paths from vector_search chunks and issues `read_file` calls. This leverages the existing `_extract_file_paths_from_context` function which is currently only a fallback.

### Decision 6: Deprecate `local_file_qa` from tool list

**Choice**: Remove `local_file_qa` from `ALL_TOOLS` so the LLM cannot select it. Keep the class file intact for potential future use. The file-discovery use case is handled by `vector_search` (which returns file paths in metadata).

## Risks / Trade-offs

- **Rule-based routing is less flexible** → Mitigated by keeping LLM planner for retry rounds; covers 90% of first-round cases correctly
- **Re-indexing required after doc_id fix** → Users must run `kb-agent index` after upgrade; document in release notes
- **Removing `local_file_qa` changes user workflow** → Users who relied on numbered file lists will need to ask differently; `vector_search` results include file paths
- **Synthesis prompt may produce overly verbose answers** → Acceptable trade-off; users complained about terse answers, and they can always ask for summaries

## Open Questions

- Should we add a `--clean` flag to `kb-agent index` that removes old `.docx.md` files before re-indexing?
- Should `read_file` auto-expand use a configurable line range (currently proposed ±100 lines)?
