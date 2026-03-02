## ADDED Requirements

### Requirement: /index Slash Command
The system SHALL provide an `/index` chat command that allows users to seamlessly ingest external resources (URLs, Jira tickets, Confluence pages) directly into the knowledge base vector store from the TUI.

#### Scenario: User indexes a web URL
- **WHEN** the user types `/index https://example.com` in the TUI chat input
- **THEN** the system automatically routes the request to the WebConnector, fetches the page content, converts it to Markdown, saves the file to the index directory, ingests the chunks into the vector database, and displays a success message.

#### Scenario: User indexes a Jira ticket
- **WHEN** the user types `/index PROJ-1234` in the TUI chat input
- **THEN** the system automatically routes the request to the JiraConnector, fetches the ticket content, converts it to Markdown, saves the file to the index directory, ingests the chunks into the vector database, and displays a success message.

#### Scenario: User indexes a Confluence Document
- **WHEN** the user types `/index 987654321` (a numeric Confluence page ID) in the TUI chat input
- **THEN** the system automatically routes the request to the ConfluenceConnector, fetches the page content, converts it to Markdown, saves the file to the index directory, ingests the chunks into the vector database, and displays a success message.

#### Scenario: Error handling for invalid external resource
- **WHEN** the user types `/index invalid-resource` or fetching the resource fails
- **THEN** the system displays a descriptive error message in the TUI indicating the failure and does not crash the application.
