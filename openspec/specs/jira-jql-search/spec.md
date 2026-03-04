## Purpose
Provides natural language search capabilities for Jira issues using an LLM to generate JQL.

## Requirements

### Requirement: LLM converts natural language to JQL
The system SHALL accept a natural language query describing Jira search criteria and use the configured LLM to convert it into a valid JQL string before executing the search.

#### Scenario: Simple natural language query
- **WHEN** the user asks "my unresolved tasks"
- **THEN** the system generates JQL like `assignee = currentUser() AND resolution = Unresolved ORDER BY updated DESC` and executes it

#### Scenario: Complex natural language query
- **WHEN** the user asks "high priority bugs updated this week in project PROJ"
- **THEN** the system generates JQL like `project = PROJ AND priority in (High, Highest) AND type = Bug AND updated >= startOfWeek() ORDER BY updated DESC` and executes it

### Requirement: jira_jql agent tool registration
The system SHALL register a `jira_jql` LangChain tool that accepts a natural language query string and returns JSON-formatted Jira issue results.

#### Scenario: Tool is available to the agent planner
- **WHEN** the agent planner processes a query about searching/listing Jira issues
- **THEN** the planner SHALL be able to select `jira_jql` as a tool to call

### Requirement: Agent routing for Jira search intent
The `DECOMPOSE_SYSTEM` prompt SHALL detect Jira search intent (e.g., "my tasks", "unresolved bugs", "本周更新的任务") and route to the `jira_jql` tool instead of `jira_fetch`.

#### Scenario: Search intent detected
- **WHEN** the user asks "查询我的未解决的 Jira 任务"
- **THEN** the decompose node routes to `jira_jql` with the natural language query

#### Scenario: Specific ticket still routes to jira_fetch
- **WHEN** the user asks about "PROJ-123"
- **THEN** the decompose node routes to `jira_fetch` (not `jira_jql`)

### Requirement: JQL error handling
The system SHALL catch invalid JQL errors and return a user-friendly message that includes the generated JQL for debugging.

#### Scenario: Invalid JQL generated
- **WHEN** the LLM generates syntactically invalid JQL
- **THEN** the system returns an error message containing the attempted JQL string and the error details

### Requirement: Jira Markdown includes sub-tasks
The Jira issue Markdown output SHALL include a "Sub-Tasks" section with a table listing each sub-task's key (as a link), summary, status, and assignee.

#### Scenario: Issue with sub-tasks
- **WHEN** a Jira issue has sub-tasks
- **THEN** the Markdown output includes a `## Sub-Tasks` section with a table containing columns: Key, Summary, Status, Assignee

#### Scenario: Issue without sub-tasks
- **WHEN** a Jira issue has no sub-tasks
- **THEN** the `## Sub-Tasks` section is omitted from the output

### Requirement: Jira Markdown includes issue links
The Jira issue Markdown output SHALL include a "Related Issues" section with a table listing each linked issue's relationship type, key (as a link), summary, and status.

#### Scenario: Issue with links
- **WHEN** a Jira issue has issue links (blocks, is blocked by, relates to, etc.)
- **THEN** the Markdown output includes a `## Related Issues` section with a table containing columns: Relationship, Key, Summary, Status

#### Scenario: Issue without links
- **WHEN** a Jira issue has no issue links
- **THEN** the `## Related Issues` section is omitted from the output

### Requirement: Connector uses atlassian-python-api
The `JiraConnector` SHALL use `atlassian.Jira` client instead of raw `requests` calls, with PAT authentication via the `token=` parameter.

#### Scenario: Successful initialization
- **WHEN** `JiraConnector` is instantiated with a valid base_url and token
- **THEN** it creates an `atlassian.Jira` instance with PAT auth
