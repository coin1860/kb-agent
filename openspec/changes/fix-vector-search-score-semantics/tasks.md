## 1. Configuration & Tooling Updates

- [x] 1.1 Update `config.py` default `vector_score_threshold` from `0.5` to `0.3`.
- [x] 1.2 Update `VectorTool.search` in `vector_tool.py` to convert ChromaDB distance to similarity (`score = 1.0 - distance`).
- [x] 1.3 Update the filtering logic in `VectorTool.search` to discard chunks where `score < threshold` (instead of `distance >= threshold`).

## 2. UI and Consumers Alignment

- [x] 2.1 Update `_run_file_search` in `tui.py` to sort vector results by `score` in **descending** order (highest similarity first).
- [x] 2.2 Update `_run_query` log logic in `tui.py` (Sources section) to format the new 0.0-1.0 raw similarity score cleanly (without the previous `1 - score/2` pseudo-conversion).
- [x] 2.3 Verify `grade_evidence_node` in `agent/nodes.py` still correctly compares `score >= score_threshold` using the new similarity score.

## 3. Testing 

- [x] 3.1 Create or update unit test `tests/test_vector_tool.py` to assert that output scores are on a 0.0-1.0 similarity scale.
- [x] 3.2 Add test case verifying that `VectorTool.search` correctly filters strictly *below* the similarity threshold.
