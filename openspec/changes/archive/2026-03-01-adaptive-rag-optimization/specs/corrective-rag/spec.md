## ADDED Requirements

### Requirement: Grade each evidence item for relevance
The system SHALL score each retrieved context item on a 0.0–1.0 relevance scale against the original query using an LLM-based grader.

#### Scenario: Batch relevance grading
- **WHEN** the `grade_evidence` node receives N context items
- **THEN** the system sends all items to the LLM in a single batch call
- **AND** the LLM returns a JSON array of N float scores (0.0–1.0)
- **AND** scores are stored in `AgentState.evidence_scores`

#### Scenario: Grading with parse failure fallback
- **WHEN** the LLM grader output cannot be parsed as valid JSON scores
- **THEN** the system assigns a default score of 0.5 to all items
- **AND** the system logs a warning via `log_audit`

### Requirement: Filter low-relevance evidence
The system SHALL discard context items with relevance score below 0.3 before synthesis to prevent noise contamination.

#### Scenario: Low-score evidence removed
- **WHEN** a context item has a relevance score < 0.3
- **THEN** the item is removed from `AgentState.context`
- **AND** the removal is logged via `log_audit`

#### Scenario: All evidence below threshold
- **WHEN** all context items score below 0.3
- **THEN** the system triggers a RE-RETRIEVE action instead of synthesizing with no evidence

### Requirement: Adaptive decision based on aggregate score
The system SHALL compute the average relevance score of remaining evidence and route to one of three actions: GENERATE, REFINE, or RE-RETRIEVE.

#### Scenario: High-quality evidence triggers GENERATE
- **WHEN** the average score of filtered evidence is ≥ 0.7
- **THEN** `AgentState.grader_action` is set to `"GENERATE"`
- **AND** the graph routes to the `synthesize` node

#### Scenario: Mixed-quality evidence triggers REFINE
- **WHEN** the average score of filtered evidence is ≥ 0.3 and < 0.7
- **THEN** `AgentState.grader_action` is set to `"REFINE"`
- **AND** the system retains items with score ≥ 0.3 in context
- **AND** the graph routes back to `plan` to search for additional evidence with refined keywords

#### Scenario: Poor evidence triggers RE-RETRIEVE
- **WHEN** the average score of filtered evidence is < 0.3 (or no evidence remains)
- **THEN** `AgentState.grader_action` is set to `"RE_RETRIEVE"`
- **AND** the graph routes back to `analyze_and_route` to try a different retrieval strategy

#### Scenario: Max iterations reached regardless of score
- **WHEN** `AgentState.iteration` reaches `KB_AGENT_MAX_ITERATIONS`
- **THEN** the system routes to `synthesize` regardless of grader action
- **AND** the system uses whatever evidence is available (even if low-scored)
