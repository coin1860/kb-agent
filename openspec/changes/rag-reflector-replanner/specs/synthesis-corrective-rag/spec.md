## MODIFIED Requirements

### Requirement: Adaptive decision based on aggregate score
The system SHALL compute the average relevance score of remaining evidence and assign one of three actions: GENERATE, REFINE, or RE-RETRIEVE. The `grade_evidence_node` SHALL NOT make the final routing decision; instead, all flows SHALL proceed to the `reflect_node` for entity extraction and task planning.

#### Scenario: High-quality evidence triggers GENERATE
- **WHEN** the average score of filtered evidence is ≥ 0.7
- **THEN** `AgentState.grader_action` is set to `"GENERATE"`
- **AND** the graph routes to the `reflect_node` for final precision evaluation

#### Scenario: Mixed-quality evidence triggers REFINE
- **WHEN** the average score of filtered evidence is ≥ 0.3 and < 0.7
- **THEN** `AgentState.grader_action` is set to `"REFINE"`
- **AND** the system retains items with score ≥ 0.3 in context
- **AND** the graph routes to the `reflect_node` 

#### Scenario: Poor evidence triggers RE-RETRIEVE with preserved hints
- **WHEN** the average score of filtered evidence is < 0.3 (or no evidence remains)
- **THEN** `AgentState.grader_action` is set to `"RE_RETRIEVE"`
- **AND** the graph routes to the `reflect_node` 

#### Scenario: Max iterations reached regardless of score
- **WHEN** `AgentState.iteration` reaches `KB_AGENT_MAX_ITERATIONS`
- **THEN** the system still routes to `reflect_node` regardless of grader action
- **AND** the system uses whatever evidence is available (even if low-scored)
