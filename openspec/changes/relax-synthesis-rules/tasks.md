## 1. Relax Grader Logic

- [x] 1.1 Update `grade_evidence_node` in `src/kb_agent/agent/nodes.py` to remove the hard filter that discards context items with `score < 0.3`. Alternatively, lower the threshold to `> 0.0`. All somewhat relevant items should pass to the synthesizer.

## 2. Update Synthesizer Prompt

- [x] 2.1 Update `SYNTHESIZE_SYSTEM` in `src/kb_agent/agent/nodes.py` to prompt the LLM to provide a "best-effort" answer when context is partial, explicitly removing the strict instruction to always reply "I couldn't find relevant information..." unless the context is genuinely completely unrelated or empty.
- [x] 2.2 Add instructions to `SYNTHESIZE_SYSTEM` allowing the LLM to use limited general knowledge to interpret or glue facts together, but requiring it to clearly state when it is making assumptions.

## 3. Testing and Validation

- [x] 3.1 Run `test_query.py` or the CLI against complex queries that previously failed due to "insufficient context" to ensure they now return partial, best-effort answers with citations.
- [x] 3.2 Verify that the token truncation limits (max 20 items, 2000 chars each) in `grade_evidence_node` safely handle the increased volume of context items passed to the synthesizer.
