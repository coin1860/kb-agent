## Why

The current RAG flow has overly strict synthesis and evidence grading rules that lead to a poor user experience. Specifically, the grader aggressively filters out partially relevant chunks (score < 0.3), and the synthesizer is instructed to strictly refuse answering ("I couldn't find relevant information...") if the evidence is deemed incomplete. This results in the agent acting like a brittle "repeater" that fails to answer queries that could have been partially addressed or reasoned about. The goal is to relax these constraints to prioritize a "best-effort" response (aiming for ~85% accuracy and much higher recall) rather than insisting on 100% complete evidence.

## What Changes

- Modify `grade_evidence_node` to stop aggressively discarding context items scoring below 0.3. All retrieved (and potentially relevant) context will be passed to the synthesizer.
- Update `SYNTHESIZE_SYSTEM` prompt to instruct the LLM to provide a "best-effort" answer, allowing it to synthesize whatever partial information is available, and use general reasoning to assist the explanation (while still primarily grounding in the provided context).
- Ensure the system does not prematurely drop contexts when transitioning from `RE_RETRIEVE` to `synthesize` in edge cases where iterations run out.

## Capabilities

### New Capabilities
None.

### Modified Capabilities
- `rag-synthesis`: The rules governing how the agent synthesizes answers from evidence are being relaxed to allow for partial answers and best-effort reasoning instead of strict refusal.
- `evidence-grading`: The relevance threshold for retaining context items is being removed or significantly lowered to preserve maximum information for the synthesizer.

## Impact

- `src/kb_agent/agent/nodes.py`: Changes to `grade_evidence_node` filtering logic and `SYNTHESIZE_SYSTEM` prompt.
- User Experience: The agent will provide more helpful, partial answers instead of frequently failing with "I couldn't find relevant information."
