## 1. Jira Connector Refactor

- [x] 1.1 Replace `requests` with `atlassian-python-api` in `JiraConnector.__init__` using PAT authentication
- [x] 1.2 Update `JiraConnector._format_issue` to include Sub-Tasks and Related Issues tables in Markdown
- [x] 1.3 Add `jql_search(natural_query)` method to `JiraConnector` using `LLMClient` to convert to JQL and execute
- [x] 1.4 Test Jira issue fetching and formatting to ensure compatibility with `fetch_data`

## 2. Confluence Connector Refactor

- [x] 2.1 Replace `requests` with `atlassian-python-api` in `ConfluenceConnector.__init__` using PAT authentication
- [x] 2.2 Re-implement `ConfluenceConnector.fetch_data` / `_format_page` using `atlassian-python-api`
- [x] 2.3 Implement `ConfluenceConnector.crawl_tree` with BFS traversal, depth limit, and progress callback

## 3. Agent Integration

- [x] 3.1 Create new `@tool jira_jql(query)` in `src/kb_agent/agent/tools.py`
- [x] 3.2 Add `jira_jql` to `ALL_TOOLS` and update `TOOL_DESCRIPTIONS`
- [x] 3.3 Update `_is_tool_applicable` and `_build_tool_args` in `src/kb_agent/agent/nodes.py` to support `jira_jql`
- [x] 3.4 Update `DECOMPOSE_SYSTEM` prompt in `src/kb_agent/agent/nodes.py` to route Jira semantic queries to `jira_jql`

## 4. TUI /sync_confluence Command

- [x] 4.1 Create `ConfluenceSyncScreen(ModalScreen)` in `src/kb_agent/tui.py` for Root Page ID and Crawl Depth options
- [x] 4.2 Add `/sync_confluence` to `SLASH_COMMANDS` and `_exec_slash` in `KBAgentApp`
- [x] 4.3 Implement `_run_confluence_sync` async worker to trigger crawler, manage progress logs, and write files to `source/confluence/`

## 5. End-to-End Verification

- [x] 5.1 Test `/sync_confluence` from TUI and verify markdown files are correctly generated in `source/confluence/`
- [x] 5.2 Test `kb-agent index` to ensure it continues to pick up indexed items from `confluence/` correctly
- [x] 5.3 Test Jira semantic queries through chat interface (e.g., "query my unresolved tasks")
- [x] 5.4 Test Jira specific queries through chat interface (e.g., "PROJ-123") and check markdown formatting
