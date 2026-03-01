## Why

The current TUI provide limited feedback during search execution. Users only see the total number of characters retrieved, which doesn't reflect the structural success of the search (e.g., how many files were matched or how many knowledge chunks were found). Additionally, the use of "local_file" as a source identifier in citations is confusing and lacks the actual file path.

## What Changes

- **Search Statistics**: Enhance tool execution logs in the TUI to show:
  - For `grep_search`: Number of unique files matched.
  - For `vector_search`/`hybrid_search`: Number of knowledge chunks retrieved.
- **Improved Citations**: Fix the source resolution logic to prioritize actual file paths over internal connector identifiers like "local_file".

## Capabilities

### New Capabilities
- None

### Modified Capabilities
- `hybrid-retrieval`: The system feedback during retrieval SHALL be more descriptive, providing counts of files/chunks to the user.

## Impact

- `src/kb_agent/agent/nodes.py`: `tool_node` and citation formatting logic will be updated.
