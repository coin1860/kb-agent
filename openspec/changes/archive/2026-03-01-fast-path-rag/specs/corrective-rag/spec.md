## MODIFIED Requirements

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
