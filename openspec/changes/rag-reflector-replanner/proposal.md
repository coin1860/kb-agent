## Why

Currently, the Agentic RAG pipeline's failure recovery strategy is limited to blindly re-running vector searches or falling back to LLM synthesis when the context is insufficient. The system cannot perform "detective-style" reflection to discover and actively pursue new entities (like Jira IDs or Confluence Page IDs) hidden within the initially retrieved semantic context, leading to a loss of precision entirely available within the existing context.

## What Changes

- Add a new `reflect_node` directly after `grade_evidence_node` to extract precise entities (Jira/Confluence IDs) from retrieved contexts using zero-shot Regex templates.
- Enhance the `AgentState` schema to include short-term "task queue" memory (`discovered_entities`, `task_queue`, `attempted_task_ids`) to track identified entities across iterations without duplicating work.
- Modify `plan_node` to include a zero-LLM "precision loop" which pulls executable tasks from the task queue when working on subsequent context retrieval loops.
- Modify `grade_evidence_node` and its existing fast-path logic to route cleanly into the new `reflect_node`.
- Enhance `synthesize_node` to explicitly acknowledge specific "knowledge gaps" if iteration caps are reached without fulfilling the task queue.

## Capabilities

### New Capabilities
- `reflection-replanning`: The ability for the agent to actively extract precise entity IDs from semantic documents without LLM calls, and append them to a stateful task queue for precise tool fetching on subsequent loops.

### Modified Capabilities
- `synthesis-corrective-rag`: The fallback corrective loop mechanism is being transitioned from simple LLM `grade_evidence` fallback strings to a stateful `reflection_verdict` and `task_queue` architecture.

## Impact

- `src/kb_agent/agent/state.py`: Schema gets extended with 5 new tracking/queue fields.
- `src/kb_agent/agent/nodes.py`: `reflect_node` is created; `plan_node` is significantly updated with a zero-LLM fast path for queued tasks; `synthesize_node` is tweaked to report gaps.
- `src/kb_agent/agent/graph.py`: Graph topology is updated. `grade_evidence` now uniformly flows into `reflect_node`, which directs traffic to `plan`, `synthesize`, or ends the iteration cycle early.
- Performance: Overall latency goes down when discovering new entities because the precision loop bypasses an LLM call at `plan_node` and `reflect_node` is pure regex.
