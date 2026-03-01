## MODIFIED Requirements

### Requirement: Document reading with explicit error reporting
The system SHALL provide a `read_file` tool that returns the full content of a file or a detailed error message if the read fails.

#### Scenario: File read success
- **WHEN** `read_file(path)` is called with a valid path within `allowed_paths`
- **THEN** the system SHALL return the UTF-8 text content of the file.

#### Scenario: File not found
- **WHEN** `read_file(path)` is called with a path that does not exist but is within `allowed_paths`
- **THEN** the system SHALL return an error message starting with `[ERROR: NOT_FOUND]`.

#### Scenario: Access denied
- **WHEN** `read_file(path)` is called with a path outside `allowed_paths`
- **THEN** the system SHALL return an error message starting with `[ERROR: ACCESS_DENIED]`
- **AND** the message SHALL include the list of currently allowed base directories.
