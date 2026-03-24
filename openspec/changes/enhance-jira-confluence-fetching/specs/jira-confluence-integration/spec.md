## ADDED Requirements

### Requirement: Fetch Recent Jira Comments
The system SHALL retrieve the most recent comments for a requested Jira issue, up to a maximum limit of 10.

#### Scenario: Single Jira issue with many comments
- **WHEN** the `jira_fetch` tool is executed for an issue that has 20 comments
- **THEN** it fetches the comment history
- **AND** it appends only the 10 most recent comments to the formatted issue output

### Requirement: Proactive Linked Confluence Fetching
The system SHALL proactively fetch content for Confluence pages linked inside a Jira issue's description or comments to a depth of 1 level.

#### Scenario: Jira issue containing Confluence references
- **WHEN** the Jira description or retrieved comments contain Confluence page URLs
- **THEN** the system parses the Confluence page IDs from these URLs
- **AND** fetches the page content via `ConfluenceConnector`
- **AND** appends the fetched markdown content inline to the Jira issue output

#### Scenario: Do not recurse Confluence links
- **WHEN** a proactively fetched Confluence page contains links to other Confluence pages
- **THEN** the system explicitly SHALL NOT follow those nested links
- **AND** stops at depth 1

### Requirement: Wrap Structural Lists with Extraction Markers
The system SHALL wrap non-content sections (specifically 'Sub-Tasks' and 'Related Issues') with section markers (`<!-- NO_ENTITY_EXTRACT -->` and `<!-- /NO_ENTITY_EXTRACT -->`) so other modules know to ignore these sections for automated relationship traversing.

#### Scenario: Formatting Sub-Tasks
- **WHEN** a Jira issue has sub-tasks
- **THEN** the list of sub-tasks is rendered in the final output
- **AND** it is wrapped entirely within `<!-- NO_ENTITY_EXTRACT -->` and `<!-- /NO_ENTITY_EXTRACT -->`

### Requirement: Unified Jira Caching
The system SHALL cache the final, fully-assembled string (including the Jira description, comments, and inline Confluence content) instead of caching partial segments.

#### Scenario: Subsequent fetches of the same issue
- **WHEN** an issue is fetched again within the cache TTL without `force_refresh`
- **THEN** the fully formatted text (with comments and confluence context previously resolved) is returned instantaneously from cache
