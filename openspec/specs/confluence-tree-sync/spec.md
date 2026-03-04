## Purpose
Provides the ability to crawl and sync entire Confluence page trees using a depth-first or breadth-first approach up to a specific depth limit.

## Requirements

### Requirement: BFS page tree crawling with depth limit
The `ConfluenceConnector` SHALL provide a `crawl_tree(root_page_id, max_depth, on_progress)` method that performs BFS traversal of the Confluence page tree, starting from the specified root page, up to `max_depth` levels deep (maximum 3).

#### Scenario: Crawl with depth 2
- **WHEN** `crawl_tree("12345", max_depth=2)` is called
- **THEN** the system fetches the root page (depth 0), its child pages (depth 1), and their child pages (depth 2), but not deeper

#### Scenario: Crawl with depth 0
- **WHEN** `crawl_tree("12345", max_depth=0)` is called
- **THEN** only the root page itself is fetched

#### Scenario: Progress callback
- **WHEN** `on_progress` callback is provided
- **THEN** it is called with `(count, page_title)` after each page is fetched

### Requirement: Pages saved to source/confluence directory
Synced Confluence pages SHALL be saved as Markdown files to `source/confluence/` with the naming pattern `{space_key}_{page_id}_{safe_title}.md`.

#### Scenario: Page saved with correct naming
- **WHEN** a page with space "DEV", ID "12345", title "Architecture Guide" is synced
- **THEN** it is saved as `source/confluence/DEV_12345_Architecture_Guide.md`

#### Scenario: Special characters in title
- **WHEN** a page title contains special characters (e.g., "API & Design / Overview")
- **THEN** special characters are replaced with underscores in the filename

### Requirement: /sync_confluence TUI command
The TUI SHALL provide a `/sync_confluence` slash command that opens a modal dialog for configuring and triggering a Confluence sync.

#### Scenario: Command appears in palette
- **WHEN** user types `/sync` in the TUI input
- **THEN** `/sync_confluence` appears in the command palette

#### Scenario: Modal dialog inputs
- **WHEN** user selects `/sync_confluence`
- **THEN** a modal dialog appears with fields for Root Page ID (text input) and Crawl Depth (1-3 selection)

### Requirement: Async sync with progress display
The Confluence sync SHALL execute asynchronously in a background thread, displaying progress in the chat log.

#### Scenario: Progress during sync
- **WHEN** sync is running
- **THEN** each fetched page appears in the chat log with its page number and title

#### Scenario: Sync completion
- **WHEN** all pages are synced
- **THEN** the chat log shows the total page count, output directory, and a reminder to run `kb-agent index`

### Requirement: Connector uses atlassian-python-api
The `ConfluenceConnector` SHALL use `atlassian.Confluence` client instead of raw `requests` calls, with PAT authentication via the `token=` parameter.

#### Scenario: Successful initialization
- **WHEN** `ConfluenceConnector` is instantiated with a valid base_url and token
- **THEN** it creates an `atlassian.Confluence` instance with PAT auth
