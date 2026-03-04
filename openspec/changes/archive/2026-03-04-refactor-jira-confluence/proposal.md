## Why

The current Jira and Confluence connectors use raw `requests` calls to interact with Atlassian APIs, resulting in manual URL construction, header management, and authentication handling. The `atlassian-python-api` library (already declared as a dependency) provides a mature, well-typed client that handles all of this automatically. Additionally, the Jira Markdown output lacks sub-task and issue link information, there's no support for semantic JQL queries (e.g., "show my unresolved tasks"), and Confluence has no ability to recursively crawl page trees for bulk indexing.

## What Changes

- **Replace `requests` with `atlassian-python-api`** in both `JiraConnector` and `ConfluenceConnector`, using PAT authentication for Jira Server/DC.
- **Enhance Jira Markdown output** to include Sub-Tasks table and Related Issues table with clickable links.
- **Add `jira_jql` agent tool** that uses LLM to convert natural language queries into JQL, then executes the query and returns formatted results.
- **Add Confluence page tree crawling** (`crawl_tree` method) with BFS traversal and configurable depth limit (max 3 levels).
- **Add `/sync_confluence` TUI command** with a modal dialog for entering root Page ID and crawl depth, async execution with progress display, saving pages as Markdown files to `source/confluence/`.
- **Update agent routing** so the planner can detect Jira search intent and route to the new `jira_jql` tool.

## Capabilities

### New Capabilities
- `jira-jql-search`: Natural language to JQL conversion and execution via a new agent tool, enabling queries like "my unresolved tasks" or "high priority bugs updated this week".
- `confluence-tree-sync`: Recursive Confluence page tree crawling (BFS, max 3 levels deep) with TUI command `/sync_confluence`, storing pages as Markdown in `source/confluence/` for subsequent indexing.

### Modified Capabilities
- (none — the changes are additive/internal refactoring with no spec-level behavior changes to existing capabilities)

## Impact

- **Code**: `connectors/jira.py`, `connectors/confluence.py`, `agent/tools.py`, `agent/nodes.py`, `tui.py`, `engine.py`
- **Dependencies**: `atlassian-python-api` (already declared in `pyproject.toml`)
- **APIs**: `BaseConnector` interface preserved (`fetch_data`, `fetch_all`), new methods added
- **Storage**: New `source/confluence/` subdirectory for synced Confluence pages
- **Agent tools**: New `jira_jql` tool added to `ALL_TOOLS`; `DECOMPOSE_SYSTEM` prompt updated for routing
