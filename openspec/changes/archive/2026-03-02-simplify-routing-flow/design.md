## Context

The current RAG implementation uses a 6-node adaptive topology where a dedicated `analyze_and_route` node attempts to parse the user's query into a complex JSON object (`sub_questions`, `search_keywords`, etc.). This parsed intent is heavily relied upon by a `hybrid_search` tool that attempts to combine keyword (Grep) and semantic (Vector) search. Over recent iterations, this approach has proven fragile:
1.  **High LLM Failure Rate:** The routing node often fails to generate valid structured JSON for keyword extraction, leading to heavy fallback logic.
2.  **Ineffective Grep:** Fallbacks often cause `hybrid_search` to pass entire natural language sentences into Ripgrep, yielding 0 results.
3.  **Flawed Result Deduplication:** The RRF (Reciprocal Rank Fusion) logic within `hybrid_search` deduplicates by file path. If a file has a low-quality keyword match early on and a high-quality semantic match later, the vector result is discarded.

To meet the goal of robustly answering questions with ~85% accuracy without over-engineering, we need to simplify the architecture, relying more on the LLM's emergent ability to utilize tools in parallel directly from the planning phase.

## Goals / Non-Goals

**Goals:**
-   Eliminate the `analyze_and_route` node and its complex JSON schema requirements.
-   Simplify the `plan_node` to handle both routing and tool selection naturally.
-   Remove the brittle `hybrid_search` tool wrapper and rely on the `plan_node` to orchestrate parallel `grep_search` and `vector_search` calls when necessary.
-   Rely on `grade_evidence` to evaluate and filter the combined pool of results from parallel parallel tool executions.

**Non-Goals:**
-   Changing the underlying vector database (ChromaDB) or keyword search engine (Ripgrep).
-   Modifying the indexing pipeline.
-   Introducing new models or changing the provider.

## Decisions

### D1: Architectural Simplification (Removing `analyze_and_route`)
**Decision:** We will remove `analyze_and_route_node` entirely. The workflow will start directly at the `plan_node` (except for a lightweight semantic check for pure chit-chat if absolutely necessary, but preferably handled within `plan_node` returning an immediate synthetic generation step).
**Rationale:** The complexity of forcing the LLM to pre-compute precise search strategies structured as JSON sub-questions is unnecessary. LLMs are highly capable of reading a user prompt and deciding, "I need to search for the exact term X, and concepts related to Y", outputting multiple tool calls in one go.
**Alternatives Considered:** Prompt engineering the analysis node to be simpler. *Rejected because it still inserts an unnecessary serialized LLM call before any actual retrieval happens.*

### D2: Delegating "Hybrid" Search to the Planner
**Decision:** We will delete the `hybrid_search` tool wrapper. Instead, the system prompt for `plan_node` will be updated to explicitly encourage issuing *both* `grep_search(query="exact keyword")` and `vector_search(query="full context")` as separate parallel tools in the same JSON array if the query demands it.
**Rationale:** LangGraph and modern LLMs support parallel tool calling natively. This removes the need for custom, buggy RRF deduplication logic in Python. The `tool_node` will execute both, append all resulting chunks to the state context, and let the `grade_evidence` node reading-comprehend which chunks are actually useful.
**Alternatives Considered:** Fixing the deduplication bug in the existing Python `hybrid_search`. *Rejected because the fallback logic of extracting exact keywords from complex sentences in Python before calling Ripgrep remains inherently brittle.*

### D3: State Simplification
**Decision:** Strip the `AgentState` of `sub_questions`, `routing_plan`, and `query_type` fields.
**Rationale:** These fields were artificial constructs created by and for the `analyze_and_route` node. Without it, the state only needs to track conversation history, raw query, gathered context, and iteration counts.

## Risks / Trade-offs

-   [Risk] **Planner might struggle with complex keyword extraction:** If the planner generates poor single keywords for `grep_search`, grep will still fail.
    -   *Mitigation:* The `plan_node` system prompt must clearly show examples of good keyword extraction vs semantic queries. Because we run it in parallel with `vector_search`, a failed grep call does not halt the pipeline; the vector results act as a robust safety net.
-   [Risk] **Context Bloat:** Firing both vector and grep searches independently might gather redundant chunks, increasing the token load on `grade_evidence` and `synthesize`.
    -   *Mitigation:* Keep the Top-K limit on individual tool outputs low (e.g., 5-10 each). The `grade_evidence` node already acts as a filter to drop irrelevant or highly redundant low-scoring chunks before generation.
