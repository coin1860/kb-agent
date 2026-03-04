---
title: Corrective RAG
domain: synthesis
---

# synthesis-corrective-rag Delta Spec

## MODIFIED Requirements

### Requirement: Adaptive decision based on aggregate score
The system SHALL compute the average relevance score of remaining evidence and route to one of three actions: GENERATE, REFINE, or RE-RETRIEVE. On REFINE or RE_RETRIEVE, the system SHALL preserve file hints from discarded context for the planner to follow in the next round.

#### Scenario: High-quality evidence triggers GENERATE
- **WHEN** the average score of filtered evidence is ≥ 0.7
- **THEN** `AgentState.grader_action` is set to `"GENERATE"`
- **AND** the graph routes to the `synthesize` node

#### Scenario: Mixed-quality evidence triggers REFINE
- **WHEN** the average score of filtered evidence is ≥ 0.3 and < 0.7
- **THEN** `AgentState.grader_action` is set to `"REFINE"`
- **AND** the system retains items with score ≥ 0.3 in context
- **AND** the system SHALL extract and preserve file paths, Jira ticket IDs, and Confluence page IDs from ALL context items (including low-scored ones) into `AgentState.context_file_hints`
- **AND** the graph routes back to `plan` to search for additional evidence

#### Scenario: Poor evidence triggers RE-RETRIEVE with preserved hints
- **WHEN** the average score of filtered evidence is < 0.3 (or no evidence remains)
- **THEN** `AgentState.grader_action` is set to `"RE_RETRIEVE"`
- **AND** the system SHALL extract and preserve file paths, Jira ticket IDs, and Confluence page IDs from ALL context items (including discarded ones) into `AgentState.context_file_hints`
- **AND** the graph routes back to `plan` with `context_file_hints` available for the planner

#### Scenario: Max iterations reached regardless of score
- **WHEN** `AgentState.iteration` reaches `KB_AGENT_MAX_ITERATIONS`
- **THEN** the system routes to `synthesize` regardless of grader action
- **AND** the system uses whatever evidence is available (even if low-scored)
