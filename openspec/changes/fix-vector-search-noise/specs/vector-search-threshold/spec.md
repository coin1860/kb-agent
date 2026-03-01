## ADDED Requirements

### Requirement: Vector Search Threshold
The system SHALL discard retrieved vector chunks whose distance metric exceeds the configured `vector_score_threshold`. Default threshold MUST be 0.5.

#### Scenario: Vector search with results below threshold
- **WHEN** the `VectorTool.search` is executed and retrieves chunks with `distances[i]` < `vector_score_threshold` (for L2)
- **THEN** the chunks are included in the returned list

#### Scenario: Vector search with results above threshold
- **WHEN** the `VectorTool.search` is executed and retrieves chunks with `distances[i]` >= `vector_score_threshold`
- **THEN** the chunks are discarded and NOT included in the returned list

### Requirement: Configurable chunking sizes
The system SHALL use optimized chunk sizes for document parsing, specifically `max_chars=800` and `overlap_chars=200`, to improve relevance density.

#### Scenario: Markdown processing
- **WHEN** a `.md` file is processed by `MarkdownAwareChunker`
- **THEN** chunks are split at 800 characters or the nearest paragraph boundary
- **AND** adjacent chunks have a 200 character overlap
