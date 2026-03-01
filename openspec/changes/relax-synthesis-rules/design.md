## Context

The agentic RAG system was originally designed with strict rules to prevent hallucination. This included a hard threshold (`score < 0.3`) in the `grade_evidence_node` which aggressively discarded retrieved context chunks, and a strict `SYNTHESIZE_SYSTEM` prompt that forced the LLM to outright decline answering ("I couldn't find relevant information...") if the surviving evidence did not fully answer the question. This behavior creates a brittle user experience where queries that could be partially answered or reasoned about are entirely rejected. The goal is to shift from a "100% strict certainty" posture to an "~85% accuracy with high recall best-effort" posture.

## Goals / Non-Goals

**Goals:**
- Eliminate premature truncation of evidence in the grading phase.
- Re-prompt the synthesis node to prioritize partial answers and best-effort reasoning over outright refusal.
- Maintain source citation for any facts drawn from the context.

**Non-Goals:**
- We are not changing the embedding model or the vector search logic itself.
- We are not allowing the agent to hallucinate factual internal knowledge completely ungrounded from the company knowledge base (it should still ground facts in the text, but can use its general knowledge to interpret them).

## Decisions

**1. Lower the Relevance Threshold in the Grader:**
- *Current:* `filtered_context` excludes items where the LLM score is `< 0.3`.
- *Decision:* We will lower this threshold dramatically (e.g., to `> 0.0` or disable it completely) so that we only filter out items the LLM explicitly grades as complete garbage (`0.0`). As long as an item has even a `0.1` relevance, it gets passed to the synthesizer. This ensures maximum signal reaches the final step.

**2. Update the Synthesizer Prompt for "Best-Effort":**
- *Current:* "The answer must come ONLY from the evidence... If the context does not contain relevant information... you MUST respond with: 'I couldn't find...'"
- *Decision:* Soften this rule. 
  - Change to: "Answer the user's question primarily using the provided context."
  - Add: "If the context only partially answers the query, provide a best-effort response using the available information. You may use your general knowledge to interpret or glue these facts together, but clearly state if you are making assumptions beyond the provided text."
  - Keep the rule to fall back to "I couldn't find..." ONLY if the retrieved context is completely devoid of any related signal.

**3. Adjust the Grader Action Logic:**
- *Current:* If `avg_score < 0.3`, it forces `RE_RETRIEVE`.
- *Decision:* Keep the `RE_RETRIEVE` loop for low scores, but ensure that when `max_iterations` is hit and it routes to `synthesize`, the `filtered_context` isn't entirely wiped out. Lowering the individual item filter threshold (Decision 1) naturally fixes this.

## Risks / Trade-offs

- **Risk:** Increased Hallucination. By allowing the LLM to use general knowledge to glue facts together, it might hallucinate details about specific internal systems.
  - **Mitigation:** The prompt explicitly requires the LLM to cite its sources `[1]` for facts and clearly state when it is making an assumption or explaining a general concept not found in the text.
- **Risk:** Context Length Bloat. Passing more low-scoring items to the synthesizer consumes more tokens.
  - **Mitigation:** We previously added a hard truncation rule to limit context items to 20 items / 2000 chars each. This protects against catastrophic token limits.
