## Why

Currently, the `VectorTool` uses ChromaDB's cosine distance as its score (ranging from 0.0 to 2.0, where lower means more relevant). However, the rest of the system (including the TUI file search table, agent evaluation nodes, and user configuration) intuitively expects a standard similarity score from 0.0 to 1.0 where higher means more relevant. This semantic mismatch leads to confusing search results, broken filtering logic, and difficult configuration (e.g., users setting threshold to 1.2 to bypass it). We need to standardize the vector search score to a 0.0-1.0 similarity metric.

## What Changes

- **Distance to Similarity Conversion**: Convert ChromaDB's raw cosine distance into a cosine similarity score (`1.0 - distance`).
- **Update Filtering Logic**: Change `VectorTool.search` to filter out chunks where the calculated similarity is *less* than the configured threshold.
- **UI Display Fixes**: Update the `/file_search` command in `tui.py` to sort results by score in descending order (highest score first) and remove the redundant `(1 - score/2) * 100` conversion in the Sources display.
- **Agent Node Alignment**: Ensure the `grade_evidence_node` (which already expects "higher is better") properly interprets the new similarity score.
- **Unit Tests**: Specifically add unit tests for `VectorTool`'s search logic to guarantee the score conversion and threshold filtering function as expected.

## Capabilities

### New Capabilities

### Modified Capabilities
- `retrieval-threshold`: The vector search threshold requirement is changing from a "distance metric limit" to a "similarity metric minimum" (0.0 to 1.0, higher is better), and the evaluation scenarios will be inverted.

## Impact

- `src/kb_agent/tools/vector_tool.py`: `VectorTool.search` output and filtering.
- `src/kb_agent/tui.py`: `/file_search` sorting and Sources formatting.
- `src/kb_agent/config.py`: Default threshold context.
- `src/kb_agent/agent/nodes.py`: Vector score fast-path thresholds validation.
- `tests/test_vector_tool.py`: New unit tests for score semantic validation.
