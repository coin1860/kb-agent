---
title: Retrieval Context Expansion
domain: retrieval
---

# retrieval-context-expand Delta Spec

## MODIFIED Requirements

### Requirement: Automatic context expansion on REFINE
When the grader returns REFINE or RE_RETRIEVE action, `plan_node` SHALL use the LLM planner with enhanced prompt guidance to follow clues from previous results. The planner SHALL prioritize read_file for file paths, jira_fetch for ticket IDs, and confluence_fetch for page references, rather than defaulting to rephrased vector searches.

#### Scenario: REFINE/RE_RETRIEVE with file path clues
- **WHEN** `grader_action` is `REFINE` or `RE_RETRIEVE`
- **AND** `context_file_hints` contains file paths from previous round results
- **THEN** the LLM planner SHALL be presented with the file hints and guided to issue `read_file` calls for relevant files
- **AND** the PLAN_SYSTEM prompt SHALL instruct the planner to prioritize following clues over rephrasing searches

#### Scenario: REFINE/RE_RETRIEVE with Jira ticket clues
- **WHEN** `grader_action` is `REFINE` or `RE_RETRIEVE`
- **AND** `context_file_hints` contains Jira ticket IDs (e.g., FSR-123, WCL-456)
- **THEN** the LLM planner SHALL be guided to issue `jira_fetch` calls for those ticket IDs
- **AND** the planner SHALL NOT simply rephrase the search query

#### Scenario: REFINE/RE_RETRIEVE with no clues
- **WHEN** `grader_action` is `REFINE` or `RE_RETRIEVE`
- **AND** `context_file_hints` is empty or contains no actionable clues
- **THEN** the LLM planner SHALL fall through to the normal LLM planner for retry strategy using different keywords
