## ADDED Requirements

### Requirement: Search feedback and citations
The system SHALL provide informative feedback during search execution and accurate citations in synthesized answers.

#### Scenario: Enhanced search log feedback
- **WHEN** a search tool (`grep_search`, `vector_search`, `hybrid_search`) returns a list of results
- **THEN** the system SHALL emit a status message to the TUI including the character count
- **AND** the message SHALL include the number of unique files matched (for grep) or total chunks found (for vector/hybrid).

#### Scenario: Accurate file citations
- **WHEN** the system formats tool results for the LLM or user display
- **THEN** it SHALL prioritize using the actual file path from metadata (e.g., `path` or `file_path`) over generic source identifiers like "local_file".
