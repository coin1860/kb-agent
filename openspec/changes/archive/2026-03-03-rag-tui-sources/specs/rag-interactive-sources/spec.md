## ADDED Requirements

### Requirement: Interactive UI Source Citations
The TUI SHALL display source citations as interactive UI elements rather than plain text appended to the LLM response.

#### Scenario: Displaying RAG sources
- **WHEN** the user provides a query and the engine returns a response with sources
- **THEN** the TUI MUST render the sources as clickable links (or buttons) below the main text in the `RichLog`
- **AND** the sources MUST display the clean filename (e.g., `document.txt`) and a human-readable similarity percentage (e.g., `95%`) instead of the absolute file path and raw L2 distance.

#### Scenario: Clicking a source citation
- **WHEN** the user clicks on an interactive source citation in the TUI
- **THEN** the TUI MUST open a modal popup or expandable section displaying the full text of the cited chunk.

### Requirement: History Context Isolation
The system SHALL prevent source citations and metadata from being fed back into the LLM context during multi-turn conversations.

#### Scenario: Multi-turn formatting
- **WHEN** the agent appends its response to the conversation history
- **THEN** it MUST exclusively append the generated textual answer, stripping any interactive source links, JSON source blocks, or plain-text `Sources:` footers
- **AND** subsequent LLM turns MUST NOT see the prior turn's sources in their history payload.
