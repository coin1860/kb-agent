# corrective-rag Specification

## Purpose
Corrective RAG (CRAG) mechanism to evaluate retrieval quality and adaptively refine search strategies.

## Requirements

### Requirement: Grade each evidence item for relevance
The system SHALL apply rule-based pre-filtering before LLM grading. If any rule matches, the system SHALL skip the LLM grading call entirely and auto-approve with GENERATE action. Otherwise, the system SHALL score each retrieved context item on a 0.0–1.0 relevance scale against the original query using an LLM-based grader.

#### Scenario: Rule — read_file results auto-approve
- **WHEN** all tool calls in the current round are `read_file`
- **THEN** the system auto-approves with `grader_action: "GENERATE"` and scores of `1.0`
- **AND** no LLM grading call is made
- **AND** the system logs `fast_path_hit` with `rule_name: "read_file"`

#### Scenario: Rule — few context items auto-approve
- **WHEN** the number of context items is less than or equal to `KB_AGENT_AUTO_APPROVE_MAX_ITEMS` (default: 2)
- **THEN** the system auto-approves with `grader_action: "GENERATE"` and scores of `1.0`
- **AND** no LLM grading call is made
- **AND** the system logs `fast_path_hit` with `rule_name: "few_context"`

#### Scenario: Rule — high vector score auto-approve
- **WHEN** all context items originate from `vector_search` and their scores in `tool_history` are ≥ `KB_AGENT_VECTOR_SCORE_THRESHOLD` (default: 0.8)
- **THEN** the system auto-approves with `grader_action: "GENERATE"` and scores of `1.0`
- **AND** no LLM grading call is made
- **AND** the system logs `fast_path_hit` with `rule_name: "high_vector_score"`

#### Scenario: No rule matched — fall through to LLM grading
- **WHEN** none of the pre-filter rules match
- **THEN** the system sends all items to the LLM in a single batch call
- **AND** the LLM returns a JSON array of N float scores (0.0–1.0)
- **AND** scores are stored in `AgentState.evidence_scores`

#### Scenario: Batch relevance grading
- **WHEN** the `grade_evidence` node receives N context items and no pre-filter rule matches
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

### Requirement: Pre-filter thresholds are configurable
The system SHALL read pre-filter thresholds from environment variables, falling back to sensible defaults.

#### Scenario: Vector score threshold from environment
- **WHEN** `KB_AGENT_VECTOR_SCORE_THRESHOLD` is set in `.env`
- **THEN** the rule-based pre-filter uses that value as the high-score threshold
- **AND** the default value is `0.8` if unset

#### Scenario: Auto-approve max items from environment
- **WHEN** `KB_AGENT_AUTO_APPROVE_MAX_ITEMS` is set in `.env`
- **THEN** the rule-based pre-filter uses that value as the few-context threshold
- **AND** the default value is `2` if unset
