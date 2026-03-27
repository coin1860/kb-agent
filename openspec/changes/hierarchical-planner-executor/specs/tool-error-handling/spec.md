## MODIFIED Requirements

### Requirement: Detect and filter error results from context
The `tool_node` SHALL detect tool/connector error responses and exclude them from the evidence context to prevent the LLM from synthesizing answers based on error messages.

For **CLI skill execution**, `SkillExecutor._execute_step()` SHALL be used as the primary tool invocation delegate in the milestone sub-loop. This ensures error detection (via `_is_error_result()`), Reflect verdict, retry, and Python auto-fix are active in the primary execution path — not only in the legacy static-plan path.

#### Scenario: Connector returns error with metadata flag
- **WHEN** a tool returns a JSON result where any item has `metadata.error == True`
- **THEN** the `tool_node` SHALL NOT add the result to `AgentState.context`
- **AND** the `tool_node` SHALL log the error in `tool_history` with an `error: True` marker
- **AND** the `tool_node` SHALL emit a warning status message (e.g., `⚠️ jira_fetch returned error`)

#### Scenario: Connector returns error as dict with status field
- **WHEN** a tool returns a JSON dict with `status: \"error\"`
- **THEN** the `tool_node` SHALL NOT add the result to `AgentState.context`
- **AND** the `tool_node` SHALL log the error in `tool_history` with an `error: True` marker

#### Scenario: Non-error result passes through normally
- **WHEN** a tool returns a result without error markers
- **THEN** the `tool_node` SHALL add it to context as before (existing behavior)

#### Scenario: CLI milestone step error triggers retry via SkillExecutor
- **WHEN** a tool call inside a milestone sub-loop returns an error result
- **THEN** `SkillExecutor._execute_step()` invokes `_reflect()` and receives a `retry` verdict
- **AND** the step is retried up to `_MAX_RETRIES` times
- **AND** `_is_error_result()` is the error detection function used (consistent with existing SkillExecutor)

#### Scenario: run_python failure auto-fixed in CLI milestone path
- **WHEN** a `run_python` step in a milestone sub-loop exits with non-zero code
- **THEN** `SkillExecutor._auto_fix_python()` is invoked
- **AND** the fix attempt is displayed via `renderer.print_info()`
- **AND** a successful fix result replaces the error result in the tool history

### Requirement: Explicit no-results feedback for search tools
Search tools SHALL return a structured \"no results\" response instead of empty arrays, so the LLM can understand that the search found nothing.

#### Scenario: vector_search returns empty results
- **WHEN** `vector_search` finds no chunks above the score threshold
- **THEN** the tool SHALL return a JSON object with `status: \"no_results\"`, `tool: \"vector_search\"`, and a human-readable message
- **AND** the message SHALL suggest trying different keywords

#### Scenario: graph_related returns empty results
- **WHEN** `graph_related` finds no related entities for the given ID
- **THEN** the tool SHALL return a JSON object with `status: \"no_results\"` and a descriptive message
