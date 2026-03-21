## MODIFIED Requirements

### Requirement: Engine Agent Mode Dispatch
The Engine SHALL support `mode="agent"` in addition to existing `"knowledge_base"` and `"normal"` modes, dispatching to the agent task graph.

#### Scenario: Agent task started
- **WHEN** `Engine.start_task(goal)` is called
- **THEN** Engine creates a new session via SessionManager, initializes AgentTaskState, and invokes the agent LangGraph

#### Scenario: Agent task resumed
- **WHEN** `Engine.resume_task(session_id)` is called
- **THEN** Engine loads the session checkpoint, restores AgentTaskState, and resumes the agent LangGraph from the last checkpoint

#### Scenario: Existing RAG mode unaffected
- **WHEN** `Engine.answer_query(query, mode="knowledge_base")` is called
- **THEN** system uses the existing RAG pipeline exactly as before, with no behavior changes
