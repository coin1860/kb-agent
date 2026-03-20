## MODIFIED Requirements

### Requirement: Vector Search Threshold
The system SHALL discard retrieved vector chunks whose similarity metric falls strictly below the configured `vector_score_threshold`. Output scores MUST represent similarity on a `0.0` to `1.0` scale (higher is more similar). Default threshold MUST be `0.3`.

#### Scenario: Vector search with results below threshold
- **WHEN** the `VectorTool.search` is executed and retrieves chunks with `similarity` < `vector_score_threshold`
- **THEN** the chunks are discarded and NOT included in the returned list

#### Scenario: Vector search with results above threshold
- **WHEN** the `VectorTool.search` is executed and retrieves chunks with `similarity` >= `vector_score_threshold`
- **THEN** the chunks are included in the returned list
