## ADDED Requirements

### Requirement: Cross-Encoder Reranking
The system SHALL use a cross-encoder model to re-score and sort context chunks retrieved from vector search before passing them to the synthesis node, but ONLY if the `use_reranker` setting is enabled.

#### Scenario: Reranker Disabled
- **WHEN** the `use_reranker` setting is false
- **THEN** the system SHALL bypass the reranker and simply truncate the retrieved chunks to the top 4 based on vector search scores.

#### Scenario: Reranker Enabled
- **WHEN** the `use_reranker` setting is true
- **AND** the system has retrieved chunks via vector search
- **THEN** the system SHALL compute a cross-encoder score for each chunk against the user's original query
- **AND** the system SHALL sort the chunks descending by score and retain only the top 3 chunks for context.

### Requirement: Asynchronous Model Loading
The system SHALL load the reranker model asynchronously to prevent UI blocking.

#### Scenario: Application Startup with Reranker Enabled
- **WHEN** the application starts and `use_reranker` is true
- **THEN** the system SHALL initiate the loading of the GGUF reranker model in a background thread or asynchronous task.

#### Scenario: Query execution while model is loading
- **WHEN** a user submits a query and the graph reaches the rerank node
- **AND** the reranker model is still loading
- **THEN** the rerank node SHALL gracefully wait for the model to finish loading before proceeding.
