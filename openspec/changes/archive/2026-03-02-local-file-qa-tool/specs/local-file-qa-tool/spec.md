## ADDED Requirements

### Requirement: Search local files by keywords
The system SHALL provide a tool (`LocalFileQATool`) to search the local document index for files that match semantic keywords in either their filename or content.

#### Scenario: User searches for Mexico payment files
- **WHEN** the agent invokes `local_file_qa` with query "Mexico payment"
- **THEN** the tool queries ChromaDB's `kb_docs` collection
- **AND** the tool filters only for `type: "summary"` or `type: "full"`
- **AND** the tool returns a maximum of 5 distinct results

### Requirement: Format search results as 1-indexed table
The system SHALL format the returned search results as a strictly numbered vertical list, explicitly marking whether the match was found in the filename or the body context.

#### Scenario: Tool returns formatted strings to the Planner
- **WHEN** the `LocalFileQATool` retrieves matching documents
- **THEN** it formats the output exactly as:
  `1, file name1 (filename match)`
  `2, file name2 (context match)`
- **AND** it determines `(filename match)` if the query words heavily intersect with the `related_file` metadata string, otherwise `(context match)`.
