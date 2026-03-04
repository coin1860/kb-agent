## ADDED Requirements

### Requirement: Expose CSV schema tool
The system MUST provide an agent tool to retrieve the schema and sample rows of a specified `.csv` file.

#### Scenario: Agent requests schema
- **WHEN** the agent invokes `csv_info` with a filename before running a query
- **THEN** the system returns a Markdown string containing the column names, datatypes, and first 3 rows.

### Requirement: Error reporting on invalid queries
The system MUST capture exceptions during pandas dataframe query execution and return a descriptive error containing the valid column headers, enforcing a self-correction loop.

#### Scenario: Agent makes malformed query
- **WHEN** the agent provides a `csv_query` with a `condition` that references a nonexistent column
- **THEN** the query engine throws an exception
- **AND** the system catches it, returning an error message containing the valid list of headers and instructing the agent to try again.
