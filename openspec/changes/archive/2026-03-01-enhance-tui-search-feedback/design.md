## Context

The `tool_node` in `src/kb_agent/agent/nodes.py` emits a generic "Got X chars" message to the TUI. When the tool result is JSON (which it is for search tools), we can provide much better feedback by parsing that JSON and extracting record counts. Additionally, the citation formatting logic in `tool_node` currently uses a naive heuristic for identifying the source path, often resulting in "local_file" being displayed.

## Goals / Non-Goals

**Goals:**
- Provide file match counts for `grep_search`.
- Provide chunk counts for `vector_search` and `hybrid_search`.
- Fix citation formatting to use actual file paths.

**Non-Goals:**
- Changing the underlying search tools' return formats.
- Adding complex UI elements (this is strictly log/string enhancement).

## Decisions

### 1. Augment `_emit` in `tool_node`
In `tool_node`, after a tool execution, we will attempt to `json.loads` the result. 
- If successful and it's a list:
  - For `grep_search`: Count unique `file_path` entries.
  - For others: Count total items in the list.
- Append this information to the TUI status message: ` Got 1234 chars from grep_search (3 files matched)`.

### 2. Update Source Resolution in Citation Formatting
In `tool_node`'s citation formatting block, change the priority for determining the `path`:
*Old*: `path = item.get("file_path") or item.get("metadata", {}).get("source") or item.get("id")`
*New*: `path = item.get("file_path") or item.get("metadata", {}).get("path") or item.get("metadata", {}).get("source") or item.get("id")`
*Rationale*: Local file connectors store the real path in `metadata["path"]`. Internal identifiers like "local_file" should be the last resort.

## Risks / Trade-offs

- **Performance**: Parsing JSON twice (once for logs, once for citations). 
  - *Mitigation*: The JSON results are typically small (< 20 items), so impact is negligible.
- **Robustness**: Tool results might not always be JSON.
  - *Mitigation*: Use try-except blocks and only augment if parsing succeeds.
