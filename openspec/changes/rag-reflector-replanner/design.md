## Context

The existing RAG pipeline handles failure loops by sending context chunks back to an LLM evaluator, which returns `REFINE` or `RE_RETRIEVE`. The LLM planner then guesses at how to follow up with its vector search tools. When dealing with contextually mentioned explicit keys like Jira Issue keys or Confluence Page IDs, the process degrades into inaccurate vector queries. To perform well given the slow LLM token generation rate, the agent needs to transition to precise tool usages like `jira_fetch` intelligently and automatically without wasting tokens on planning and grading.

## Goals / Non-Goals

**Goals:**
- Extract exact Jira and Confluence IDs using highly performant pure regex evaluation over newly retrieved text chunks.
- Eliminate unnecessary context evaluation cycles where straightforward execution tasks are explicitly defined and required.
- Maintain tracking across loops using queue-based Task additions to the `AgentState`.
- Pass detailed explanations of explicitly missing information at the end of the extraction process to the final `synthesize_node`.
- Simplify `grade_evidence_node` handling by offloading re-route logic to `reflect_node`.

**Non-Goals:**
- Validating the precise context matching using LLM review. `reflect_node` will remain pure regex to maximize iteration speed.
- Solving semantic contradictions between the data source and the text chunk.

## Decisions

**1. New Nodes and Graph Flow**
We will create `reflect_node`, placed sequentially *after* `grade_evidence_node`. The `grade_evidence_node` will transition from executing complex conditional edge logic to returning simple LLM relevance scores. All branching goes through `reflect_node`.

**2. Regex Implementation**
The system uses exact regex formulas:
- JIRA: `r'\b[A-Z]+-\d+\b'`
- Confluence: `r'\b\d{9,}\b'`
To mitigate false positives with Confluence page definitions, we will implement mild semantic bounds: any match requires surrounding context keywords (e.g., `['confluence', '頁面', 'page', 'wiki', '查看']`).

**3. Planner Node Shortcuts**
For `iteration > 0` paths, `plan_node` checks the `task_queue` in the `AgentState`. If un-attempted structured tasks exist, the Node short-circuits to bypass all LLM invocation and return queued exact-tool invocations (`jira_fetch` or `confluence_fetch`).

**4. State Schema Update**
We introduce new elements to the `AgentState`:
- `discovered_entities`: (List) Extracted `type` and `value` entities to prevent task duplication.
- `task_queue`: (List) Pending explicitly structured tasks with tool schemas.
- `attempted_task_ids`: (List) Tracking for all processed structured tasks.
- `reflection_verdict`: (String) Enumerated values: `sufficient`, `needs_precision`, `exhausted`.
- `knowledge_gaps`: (List) Strings passed to synthesis expressing unreachable items explicitly.

## Risks / Trade-offs

- **Risk: Infinite Loop Over Exhausted Retrievable Entity Items**
  - **Mitigation:** The loop tracking limits iterations to a predefined maximum via `KB_AGENT_MAX_ITERATIONS`. Furthermore, `attempted_task_ids` permanently bans previously processed discrete string values from creating new tool cycles even if rediscovered across varied context chunks in subsequent passes.
- **Risk: False Positives for 9+ Digit Regex matches.**
  - **Mitigation:** Implemented context boundaries around pure numbered strings prior to converting the matches to `confluence_fetch` cycles. 
