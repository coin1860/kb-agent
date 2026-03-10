## Context

Currently, the agent workflow begins at `plan_node`, which is completely stateless with respect to previous conversation turns. This prevents the pipeline from understanding reference pronouns like "it" or referencing previously mentioned tools and outputs implicitly. Furthermore, it causes the agent to perform wasted retrievals when users ask simple follow-up questions that only require summarizing or extending a previous answer (e.g. "Can you translate that to English?").

## Goals / Non-Goals

**Goals:**
- Design a front-end router (`analyze_and_route`) that uses full conversation history to intelligently decide if a tool search is necessary.
- Pass explicitly resolved entities and a context-aware rewritten query down into the tool-planning phase (`plan_node`).
- Refactor the LangGraph graph topology to support conditional entry points.

**Non-Goals:**
- Creating new search tools or altering underlying storage index retrieval logic.
- Reworking the CRAG evaluation strategy (`grade_evidence_node`).

## Decisions

**Decision 1: Introduce a Dedicated Router Node (Supervisor Pattern)**
Why: Shoving routing logic into the planner creates too much complexity for a single model call. A dedicated router simplifies the `plan_node` prompt.
Alternative: Enhancing `plan_node` without another node was considered, but splitting concerns align better with LangGraph's recommended multi-agent supervisor/worker patterns. 

**Decision 2: Pass 'active_entities' And 'resolved_query' in AgentState**
Why: The planner still needs to execute Jira fetches or semantic search. Sending it explicit "hints" from the router prevents it from having to deduce context again.

**Decision 3: Direct routing to 'synthesize' for Chit-chat/Follow-ups**
Why: Token savings and lower latency. We can skip the tool loop and CRAG grading entirely if the router determines the answer exists in memory.

## Risks / Trade-offs

- [Risk] Extra LLM Call for Router: This increases baseline latency by one LLM generation step on the critical path.
  - Mitigation: The router prompt must be highly optimized, or offset by skipping long search loops when unnecessary.
- [Risk] Over-truncation of active entities.
  - Mitigation: We must ensure the `active_entities` field accurately captures identifiers like Jira numbers and page IDs.
