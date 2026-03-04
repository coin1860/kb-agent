## Context

The `kb-agent` codebase has Jira and Confluence connectors (`src/kb_agent/connectors/jira.py` and `confluence.py`) that use raw `requests` calls for REST API interaction. The `atlassian-python-api` library is already declared as a dependency (`pyproject.toml`) and installed in the environment, but not yet used by the connectors. Authentication is Jira Server/DC with PAT (Personal Access Token).

The agent system (`agent/tools.py`) exposes `jira_fetch` and `confluence_fetch` as LangChain tools, and the `DECOMPOSE_SYSTEM` prompt in `nodes.py` routes Jira ticket patterns to `jira_fetch`. Currently there is no tool for semantic JQL queries.

The TUI (`tui.py`) has a command palette with slash commands and a `SettingsScreen` that already includes Jira/Confluence URL and token fields.

## Goals / Non-Goals

**Goals:**
- Replace `requests` with `atlassian-python-api` in both connectors for cleaner code and automatic auth handling
- Enrich Jira Markdown output with sub-tasks and issue links tables
- Add `jira_jql` tool: LLM converts natural language → JQL → executes → returns formatted results
- Add `ConfluenceConnector.crawl_tree()` for BFS page tree crawling with depth limit
- Add `/sync_confluence` TUI command with modal dialog and async progress display
- Save synced Confluence pages to `source/confluence/` for manual `kb-agent index`

**Non-Goals:**
- Automatic/scheduled sync of Confluence content
- OAuth2 or Basic Auth support (PAT only for now)
- Modifying the `BaseConnector` abstract interface
- Changing the existing `kb-agent index` pipeline

## Decisions

### 1. Use `atlassian-python-api` Jira/Confluence classes directly

**Choice**: Instantiate `atlassian.Jira(url, token=token)` and `atlassian.Confluence(url, token=token)` inside the connector `__init__`.

**Rationale**: The library handles URL construction, headers, pagination, and error handling. PAT auth is supported via `token=` parameter for Server/DC.

**Alternative considered**: Keep `requests` but add a shared HTTP client class. Rejected because `atlassian-python-api` already does this better and is already a declared dependency.

### 2. Separate `jira_jql` tool from `jira_fetch`

**Choice**: Create a new `@tool jira_jql(query: str)` rather than adding JQL support to `jira_fetch`.

**Rationale**: Different semantics — `jira_fetch` is for precise lookup by issue key, `jira_jql` is for semantic search that requires LLM-driven JQL generation. Keeping them separate makes the agent's tool selection clearer.

### 3. BFS with depth limit for Confluence crawl

**Choice**: Use iterative BFS with `(page_id, depth)` tuples, stopping when `depth > max_depth`.

**Rationale**: BFS ensures breadth-first traversal (all siblings before deeper levels), predictable ordering, and simple depth control. The `get_child_pages()` API returns immediate children.

**Alternative considered**: `get_subtree_of_content_ids()` — returns all descendant IDs at once but provides no depth information, making it unsuitable for depth-limited crawling.

### 4. Store Confluence pages in `source/confluence/`

**Choice**: Save to `source/confluence/{space}_{page_id}_{safe_title}.md`.

**Rationale**: Placing under `source/` integrates with the existing `kb-agent index` pipeline which reads from `source_docs_path`. The `confluence/` subdirectory keeps content organized. `LocalFileConnector.fetch_all()` already walks subdirectories.

### 5. LLM-driven JQL generation

**Choice**: Use the existing `LLMClient` to convert natural language to JQL with a focused prompt, then execute via `Jira.jql()`.

**Rationale**: JQL syntax is complex but well-defined. An LLM with specific examples can reliably convert common queries ("my unresolved tasks", "high priority bugs") with minimal prompt engineering.

## Risks / Trade-offs

- **[Risk] LLM generates invalid JQL** → Mitigation: Wrap in try/except, return error message with the generated JQL so user can see what went wrong
- **[Risk] Large Confluence trees overwhelm at depth 3** → Mitigation: Max depth capped at 3, progress callback shows incremental status, user can cancel
- **[Risk] PAT token expiry** → Mitigation: Existing error handling in connectors catches HTTP errors and returns user-friendly messages
- **[Risk] `atlassian-python-api` version incompatibilities** → Mitigation: Already pinned `>=3.41.0` in pyproject.toml; the API is stable
