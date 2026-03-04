# Capability: CSV Query Tool

## Purpose

The CSV Query Tool allows the agent to interact with CSV data files stored in the local file system. It provides a structured way to query data using pandas conditions and retrieve specific columns, ensuring that the agent can perform data analysis tasks on structured local files.

## Requirements

### Requirement: Expose CSV schema tool
The system MUST provide an agent tool to retrieve the schema and sample rows of a specified `.csv` file.

#### Scenario: Agent requests schema
- **WHEN** the agent invokes `csv_info` with a filename before running a query
- **THEN** the system returns a Markdown string containing the column names, datatypes, and first 3 rows.

### Requirement: Process structured queries against CSV datasets
The system SHALL provide a secure mechanism to execute structured data queries on CSV files using a predefined criteria subset (conditions and column selection).

#### Scenario: Query execution on cached file
- **WHEN** a valid JSON query dictionary is provided consisting of `condition` and `columns` for a cached CSV file
- **THEN** the system returns up to 50 rows of matching data in Markdown format

#### Scenario: Fallback search sequence for files
- **WHEN** a CSV file is requested that is not in the cache
- **AND** the file exists in `archive/` or `source/`
- **THEN** the system SHALL load the file from `archive/` first, or `source/` if not in archive, into the cache before execution.

#### Scenario: Graceful constraint error handling
- **WHEN** an invalid or unsupported query condition is provided by the LLM
- **THEN** the system SHALL catch the exception and return an error message prompting the LLM to correct its format.

### Requirement: Error reporting on invalid queries
The system MUST capture exceptions during pandas dataframe query execution and return a descriptive error containing the valid column headers, enforcing a self-correction loop.


#### Scenario: Agent makes malformed query
- **WHEN** the agent provides a `csv_query` with a `condition` that references a nonexistent column
- **THEN** the query engine throws an exception
- **AND** the system catches it, returning an error message containing the valid list of headers and instructing the agent to try again.
