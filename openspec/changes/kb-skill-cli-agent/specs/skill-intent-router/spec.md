## ADDED Requirements

### Requirement: Classify user intent on every command
On every non-builtin user command, the system SHALL invoke the LLM once with: (a) a compressed skill index (each skill's `name` and `description` ≤ 15 words), and (b) the user's command text. The LLM SHALL return a JSON response classifying the intent as either `{"route": "skill", "skill_id": "<name>"}` or `{"route": "free_agent"}`.

#### Scenario: Command matches a skill
- **WHEN** user enters "生成本周 Jira 周报" and a skill named `weekly-jira-report` exists with description "Generate weekly Jira ticket summary report"
- **THEN** the router returns `{"route": "skill", "skill_id": "weekly-jira-report"}`

#### Scenario: Command does not match any skill
- **WHEN** user enters "搜索 shane 是谁" and no skill matches
- **THEN** the router returns `{"route": "free_agent"}`

#### Scenario: Ambiguous command — router picks closest match
- **WHEN** user enters a command that partially matches two skills
- **THEN** the router returns the single best match (or `free_agent` if confidence is low)

---

### Requirement: Compressed skill metadata in router prompt
The system SHALL include at most 15 words of description per skill in the routing prompt. Skill YAML `description` fields SHALL be truncated to 15 words before inclusion. The total routing prompt SHALL target under 300 tokens even with 20 skills loaded.

#### Scenario: 20 skills loaded
- **WHEN** 20 skills are loaded and a user command is entered
- **THEN** the routing LLM call uses a prompt with compressed metadata totalling <300 tokens (excluding system instructions)

---

### Requirement: Graceful handling of router parse failure
If the LLM routing response fails JSON parsing, the system SHALL default to `free_agent` routing and log a warning to the audit trail.

#### Scenario: Malformed routing response
- **WHEN** the LLM returns text that cannot be parsed as JSON
- **THEN** the system routes as `free_agent` and emits a warning; no exception is raised
