## ADDED Requirements

### Requirement: CLI session stores bidirectional conversation history
The `SkillShell` SHALL maintain a `session_messages` list containing alternating user and assistant message dicts in the format `{"role": "user"|"assistant", "content": str}`, updated after every command execution.

#### Scenario: History appended after each command
- **WHEN** a command completes execution (either via skill path or RAG path)
- **AND** a result string is returned
- **THEN** `SkillShell.session_messages` SHALL have a `{"role": "user", "content": command}` entry appended
- **AND** a `{"role": "assistant", "content": result}` entry SHALL be appended immediately after
- **AND** the order SHALL always be user → assistant alternating pairs

#### Scenario: History is empty at session start
- **WHEN** a new `SkillShell` session begins
- **THEN** `session_messages` SHALL be an empty list
- **AND** the first query SHALL be sent to RAG graph with `messages=[]`

### Requirement: Session history passed to RAG graph on each query
The CLI SHALL pass the accumulated `session_messages` into the RAG graph's `AgentState` on each invocation so that `analyze_and_route` can resolve pronoun references and cross-turn context.

#### Scenario: Pronoun reference resolved across turns
- **WHEN** the user first asks "什么是 PROJ-123？" and receives an answer
- **AND** the user then asks "它的优先级是什么？"
- **THEN** `analyze_and_route` SHALL receive the prior conversation via `messages`
- **AND** SHALL resolve "它" to "PROJ-123" and produce `resolved_query="PROJ-123 的优先级是什么？"`
- **AND** the resolved query SHALL be used for retrieval

#### Scenario: History truncated when too long
- **WHEN** `session_messages` contains more than 20 entries (10 conversation turns)
- **THEN** only the most recent 20 entries SHALL be passed to the RAG graph
- **AND** older history SHALL be silently dropped (not stored to disk)
