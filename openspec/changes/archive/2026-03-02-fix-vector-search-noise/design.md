## Context

The current `kb-agent` implementation uses `vector_search` as a fallback or parallel context gathering tool. However, the vector search simply takes the top 5 results without evaluating their absolute relevance (i.e. distance/score). Additionally, `kb_agent.agent.nodes` takes the entire JSON array output of `vector_search` and lumps it into a single context item string. 
This breaks the downstream `grade_evidence_node` filtering (CRAG), which allows queries to short-circuit the relevance grading if the context item count is <= 2. Consequently, up to 5 unrelated Markdown chunks (approaching 8000 characters) are sent directly to the LLM. 
The LLM, especially reasoning models like DeepSeek R1, wastes huge amounts of completion tokens evaluating these irrelevant chunks. A secondary issue occurs when the LLM hallucinates an `LLM Usage Stats` block by mimicking previous conversational turns, leading to duplicate or conflicting stats in the final output.

## Goals / Non-Goals

**Goals:**
- Fix the `tool_node` JSON encapsulation bug so each chunk is treated as an independent context item.
- Add a distance/score threshold to `VectorTool.search` to discard irrelevant results early.
- Configure default chunk sizing in `chunking.py` for smaller, more precise context retrieval (4000 -> 800 chars).
- Implement a regex filter in `_history_to_messages` to strip out appended `LLM Usage Stats` from conversation history to prevent hallucination.

**Non-Goals:**
- Replacing ChromaDB with a different vector engine.
- Implementing a complex, heavy Reranker model (e.g. BGE-Reranker) since the user explicitly stated they don't have a rerank API available at the bank.
- Altering the core CRAG grading prompt or its logic, other than ensuring it receives the correct item counts.

## Decisions

1. **Context Unpacking in `tool_node`**:
   Currently:
   ```python
   formatted_result = result_str # which is a JSON array of 5 items
   new_context.append(formatted_result)
   ```
   We will update this so that `if isinstance(parsed_res, list):`, we iterate through it and append *multiple* formatted strings to `new_context`. This ensures `grade_evidence_node` correctly sees 5 items instead of 1, triggering the LLM relevance grading instead of the fast-path bypass.

2. **History Filtering in `_history_to_messages`**:
   We will use `re.sub` to remove blocks like:
   ```markdown
   ---
   📊 **LLM Usage Stats:**
   - **API Calls:** ...
   - **Tokens:** ...
   ```
   from the assistant's previous messages before feeding them back into the LangChain history. This prevents the LLM from trying to autocomplete the stat block itself.

3. **Vector Score Threshold Configuration**:
   The setting `vector_score_threshold` already exists in `config.py`. We will ensure its default is set to `0.5` if empty, and modify `tools/vector_tool.py`'s `search` method to filter results:
   ```python
   if distances and distances[i] > threshold:
       continue # For L2 distance. Note: Need to verify Chroma distance metric used. 
   ```
   (Note: Chroma typically uses L2 distance or Cosine distance. If L2 is used, smaller is better. If Cosine similarity, closer to 1 is better. We need to be careful with the implementation to match the metric.)

4. **Chunk Size Reduction**:
   In `src/kb_agent/chunking.py`, we change the default `max_chars` from 4000 to 800, and `overlap_chars` from 800 to 200. This is a simpler and highly effective way to reduce the amount of irrelevant markdown text stuffed into the prompt for a single match.

## Risks / Trade-offs

- **[Risk]** Decreased default chunk size means potentially losing context if a concept spans multiple paragraphs.
  - **Mitigation**: Overlap of 200 characters helps maintain context continuity. The LLM can still use `read_file` if it needs the full document context.
- **[Risk]** Strict vector score threshold filters out "creative" albeit slightly distant matches.
  - **Mitigation**: Make the threshold easily configurable in `.env` or settings so the user can tune it.
- **[Risk]** ChromaDB Distance Metric Ambiguity.
  - **Mitigation**: Chroma's default is L2 (`l2`). We will test the threshold logic locally via `agentic-rag-architecture.md` to ensure `distances[i] < threshold` is the correct orientation.
