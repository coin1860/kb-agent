## MODIFIED Requirements

### Requirement: Classify query intent before retrieval
The system SHALL analyze each incoming query using a lightweight LLM decompose call on the first iteration. URL detection remains rule-based (pre-decompose guard). Jira ticket detection is handled by the LLM decompose step rather than hardcoded regex. The LLM planner is only used on retry rounds when decompose is not applicable.

The `analyze_and_route` node's chitchat and direct-answer detection SHALL apply universally to all callers of the RAG graph, including CLI's `free_agent` path. There is no CLI-specific routing logic inside the graph itself.

#### Scenario: First-round routing with LLM decompose
- **WHEN** `plan_node` is invoked with `iteration == 0` and no existing context
- **THEN** the system SHALL first check for URL patterns using regex (fast-path guard)
- **AND** if no URL is found, the system SHALL invoke the `_decompose_query` LLM call
- **AND** the LLM decompose call SHALL determine whether to:
  - Decompose into 3 sub-queries for parallel `vector_search` (most common case)
  - Route directly to a specific tool (e.g., `jira_fetch` for ticket IDs)
- **AND** Jira ticket detection SHALL be performed by the LLM, not by regex pattern matching

#### Scenario: URL fast-path guard (pre-decompose)
- **WHEN** `plan_node` is invoked with `iteration == 0` and the query contains a valid HTTP/HTTPS URL
- **THEN** the system SHALL route directly to `web_fetch` without invoking the decompose LLM call
- **AND** this check SHALL occur before the LLM decompose step

#### Scenario: Retry-round LLM-based planning
- **WHEN** `plan_node` is invoked with `iteration >= 1` or existing context
- **THEN** the system SHALL use the existing LLM planner with full tool descriptions
- **AND** the planner SHALL be given the file paths, ticket IDs, and page references extracted from previous round results
- **AND** the planner prompt SHALL strongly guide toward following discovered clues (read_file, jira_fetch, confluence_fetch) rather than rephrasing vector searches

#### Scenario: CLI chitchat handled by analyze_and_route without tool calls
- **WHEN** a CLI free_agent query is submitted (e.g., "hi", "谢谢")
- **AND** `analyze_and_route` classifies `route_decision="direct"`
- **THEN** the RAG graph SHALL route to `synthesize` directly
- **AND** no `plan_node` or tool calls SHALL occur
- **AND** the chitchat response SHALL be returned as `final_answer`

#### Scenario: Exact keyword query (ticket ID, config name)
- **WHEN** the user submits a query containing a specific identifier (e.g., "PROJ-123", "KB_AGENT_MAX_ITERATIONS")
- **THEN** the system classifies the query as `exact`
- **AND** the system routes primarily to `jira_fetch` (for Jira keys) or `vector_search` (for other identifiers)

#### Scenario: Conceptual or fuzzy query
- **WHEN** the user submits a conceptual question (e.g., "how does the indexing pipeline work?")
- **THEN** the system routes to `vector_search` on the first round
