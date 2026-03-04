## ADDED Requirements

### Requirement: Process structured queries against CSV datasets
The system SHALL provide a secure mechanism to execute structured data queries on CSV files using a predefined criteria subset (conditions and column selection).

#### Scenario: Query execution on cached file
- **WHEN** a valid JSON query dictionary is provided consisting of `condition` and `columns` for a cached CSV file
- **THEN** the system returns up to 50 rows of matching data in Markdown format

#### Scenario: Fallback search sequence for files
- **WHEN** a CSV file is requested that is not in the cache
- **THEN** the system SHALL search `archive/` first, and if not found, search `source/` before loading it into the cache

#### Scenario: Graceful constraint error handling
- **WHEN** an invalid or unsupported query condition is provided by the LLM
- **THEN** the system SHALL catch the exception and return an error message prompting the LLM to correct its format
