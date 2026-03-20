## Context
ChromaDB's default embedding space `cosine` returns a distance metric where `0` means identical and `1.0` means orthogonal (up to `2.0` for opposite). The `VectorTool` currently returns this raw distance as a "score". However, evaluating nodes in the AI agent (`grade_evidence_node`) and the `/file_search` display in the TUI intuitively assume that `score` represents similarity (e.g., higher is better, 0.0 to 1.0). Users are confused when setting `vector_score_threshold` because they expect a similarity cutoff, but it acts as a maximum distance limit (so setting it to 1.2 bypassing the filter).

## Goals / Non-Goals

**Goals:**
- Align the internal vector `score` returned by `VectorTool` to a standard 0.0-1.0 similarity metric.
- Ensure all downstream consumers (TUI, agent validation nodes) correctly sort and filter based on a "higher is better" similarity score.
- Prevent regression in existing tests and behaviors, adding unit tests to verify.

**Non-Goals:**
- Changing the underlying ChromaDB database distance metric (which would force all users to wipe and re-index their database).
- Altering the Reranker's scoring mechanism (which is already independent and handles its own sorting).

## Decisions

1. **Conversion Logic in VectorTool.search**:
   - *Alternative 1*: Change ChromaDB `hnsw:space` to something else. *Rejected* because it requires users to wipe their `.chroma` directory and re-index.
   - *Alternative 2*: Do nothing to the `VectorTool` and fix the display only. *Rejected* because agent nodes like `grade_evidence_node` currently compare the vector score against the threshold assuming "higher is better".
   - *Chosen*: Apply `similarity = 1.0 - distance` mapping inside `vector_tool.py`. Since embeddings are normalized, this directly converts it to Cosine Similarity.

2. **Threshold Semantics & Filtering**:
   - The config `vector_score_threshold` will now mean "minimum similarity required".
   - In `VectorTool.search`: if `similarity < threshold`, discard the chunk.
   - Update `config.py` default threshold from `0.5` to `0.3` (equivalent to allowing up to 0.7 distance, which is a sensible default for general QA).

3. **TUI Adjustments**:
   - `/file_search`: Sort descending by `score` and display it without inverted calculations.
   - Remove the `(1 - score/2) * 100` pseudo-conversion in `tui.py`'s `_run_query` Sources display, using the raw similarity score to format a clean percentage (e.g., `score * 100`).

## Risks / Trade-offs

- [Risk] Users with existing configurations over 1.0 (e.g., "1.2") will find searches fail because similarity cannot exceed 1.0. 
  → Mitigation: Clamp the threshold if it exceeds 1.0 during config load, or provide clear logging.
