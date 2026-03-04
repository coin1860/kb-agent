## Context

The current RAG pipeline in `nodes.py` uses a `plan → tool_exec → grade_evidence → (synthesize | loop)` topology. On the first iteration, `plan_node` bypasses the LLM planner entirely and sends a single `vector_search(original_query)`. When evidence is poor, the CRAG grader either triggers RE_RETRIEVE (which rephrases via the LLM planner) or REFINE (which reads files from existing context). Both retry strategies are ineffective because:
1. A single query often misses relevant chunks that different phrasings would find
2. RE_RETRIEVE discards all context, losing file path clues
3. The retry planner tends to rephrase in English for Chinese queries

The existing codebase already has `_extract_file_paths_from_context()` for REFINE file follow-up, `PLAN_SYSTEM` with tool descriptions, and rule-based URL/Jira detection via regex.

## Goals / Non-Goals

**Goals:**
- Improve first-round recall by decomposing queries into 3 sub-queries via LLM
- Make retry rounds smarter by following clues (file paths, ticket IDs) from Round 1
- Replace hardcoded Jira regex with LLM-based intent detection in the decompose step
- Keep URL detection as a fast-path regex guard (URLs are unambiguous)

**Non-Goals:**
- Changing the graph topology (plan → tool_exec → grade → synthesize remains the same)
- Adding new tools or modifying existing tool implementations
- Changing the grading algorithm or thresholds
- Supporting multi-round decomposition (only Round 1 uses decompose)

## Decisions

### Decision 1: Unified decompose-and-route LLM call for Round 1

**Choice:** Replace the current regex-based Jira detection + single `vector_search` with a single LLM call (`_decompose_query`) that both detects intent AND generates sub-queries.

**Alternatives considered:**
- Rule-based sub-query generation (e.g., keyword extraction): too brittle for Chinese text
- Separate intent classification + decompose (2 LLM calls): unnecessary overhead
- Keep regex for Jira, add decompose only for vector path: inconsistent, regex misses variant prefixes

**Output format:** The LLM returns JSON:
```json
// For vector search decomposition:
{"action": "decompose", "sub_queries": ["子查询1", "子查询2", "子查询3"]}

// For direct tool routing (Jira, etc.):
{"action": "direct", "tool": "jira_fetch", "args": {"issue_key": "FSR-123"}}
```

**URL guard stays as regex** before LLM call — URLs are structurally unambiguous and don't need LLM inference.

### Decision 2: Chunk deduplication by ID in tool_node

**Choice:** After executing multiple `vector_search` calls in `tool_node`, deduplicate formatted context items by chunk ID, keeping the highest-score copy.

**Rationale:** 3 sub-queries may return overlapping chunks from the same document section. Deduplication prevents the grader from scoring redundant evidence and keeps the context concise.

**Implementation:** Parse `[SOURCE:path:Lline:Sscore]` format from formatted items to extract ID and score for dedup.

### Decision 3: Preserve context clues via `context_file_hints` state field

**Choice:** Add a new `context_file_hints` field to `AgentState` (list of strings). On REFINE/RE_RETRIEVE, `grade_evidence_node` extracts file paths, Jira ticket IDs, and page references from ALL context items (even discarded ones) and stores them in this field.

**Rationale:** Currently RE_RETRIEVE discards all context. By preserving clue strings (not the full chunks), the next `plan_node` iteration can follow leads without re-searching.

**What goes into hints:** File paths (from `[SOURCE:path:...]`), Jira-style IDs (e.g., `FSR-123`), Confluence page IDs, URLs.

### Decision 4: Enhanced PLAN_SYSTEM prompt for retry guidance

**Choice:** Update the `PLAN_SYSTEM` prompt to include strong guidance for Round 2+:
- Present `context_file_hints` as structured clue data
- Instruct the planner to call `read_file` for file paths, `jira_fetch` for ticket IDs, `confluence_fetch` for page IDs
- Explicitly state: "rephrasing vector searches is a last resort"
- The LLM planner makes the final decision — not hardcoded rules

**Rationale:** The existing REFINE rule-based path (`_extract_file_paths_from_context → read_file`) is too narrow. Sometimes the answer is in a Jira ticket referenced in the chunks, not in the source file itself.

### Decision 5: Remove hardcoded REFINE read_file rule

**Choice:** Remove the current REFINE fast-path in `plan_node` (lines 370-377) that bypasses the LLM planner and auto-generates `read_file` calls. Instead, let the LLM planner handle all retry rounds with the enhanced prompt.

**Rationale:** The hardcoded rule only considers file paths. With `context_file_hints` containing Jira tickets and other clues, the LLM planner needs to see all available clues and decide the best follow-up action.

## Risks / Trade-offs

- **+1 LLM call on every query**: The decompose call adds latency (~0.5-1s), but eliminates most wasted retry rounds (which each cost 1-2 LLM calls). Net effect should be positive.
- **Decompose quality depends on LLM**: A poor decomposition could produce 3 irrelevant sub-queries. Mitigated by using a focused prompt and keeping the original query context.
- **Jira detection by LLM may be less reliable than regex for known patterns**: Mitigated by clear prompt instructions listing Jira key format examples. The benefit is handling varied prefixes.
- **context_file_hints could grow large**: Mitigated by capping at deduplicated, actionable clues (paths, ticket IDs) rather than storing full chunk content.
