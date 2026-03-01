# llm-usage-tracking Specification

## Purpose
Track and aggregate LLM API usage metrics (call counts and token consumption) across the entire agentic retrieval pipeline for cost and performance analysis.

## Requirements

### Requirement: Centralized tracking of LLM usage per query
The system SHALL track the number of LLM API invocations and the token consumption (prompt, completion, and total tokens) over the lifetime of a single query execution.

#### Scenario: Node invokes the LLM via the _invoke_and_track wrapper
- **WHEN** any LangGraph node (e.g., `analyze_and_route_node`, `plan_node`, `grade_evidence_node`, `synthesize_node`) calls the LLM
- **THEN** the response's token counts are extracted from the `usage_metadata` or `response_metadata`
- **AND** these values are added to the cumulative `llm_prompt_tokens`, `llm_completion_tokens`, and `llm_total_tokens` fields in the `AgentState`
- **AND** the `llm_call_count` metric in `AgentState` is incremented by 1
