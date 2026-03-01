## Why

The current vector search implementation in kb-agent suffers from several issues that lead to noisy results, bypassed evaluation filters, hallucinated LLM usage stats, and excessive processing time due to long context. Specifically:
1. `vector_search` blindly returns the top 5 results without any distance threshold filtering, meaning completely irrelevant chunks can be retrieved.
2. An encapsulation bug in `agent/nodes.py`'s `tool_node` merges these 5 returned chunks into a single large string and appends them as a single context item.
3. This single context item bypasses the `grade_evidence_node` logic (which allows <= 2 items to skip evaluation), carrying up to 7,836 characters of irrelevant data directly to the LLM.
4. DeepSeek R1 models attempt to process this large noisy context, taking up to 1,483 completion tokens in their `<think>` process, causing extreme slowdowns.
5. Models occasionally hallucinate `LLM Usage Stats` at the end of their responses by mimicking previous agent replies, resulting in double/conflicting stats.
6. The default chunk size for markdown parsing is 4000 chars, which is too large for precise vector retrieval.

## What Changes

1. **Bug Fix in Context Encapsulation (`src/kb_agent/agent/nodes.py`)**: 
   - Modify `tool_node` to parse the JSON array returned by tools (like `vector_search`) and append each chunk as an individual context item, rather than merging them into one string.
2. **Filter LLM Usage Stats Hallucinations (`src/kb_agent/agent/nodes.py`)**: 
   - In `_history_to_messages`, use a regex or string replacement to strip out the previously appended `LLM Usage Stats` blocks from history messages before sending them to the LLM.
3. **Threshold Filtering in Vector Tool (`src/kb_agent/tools/vector_tool.py`)**:
   - Update `VectorTool.search` (and `query`) to accept a threshold and filter out results whose distance/score is beyond this acceptable threshold (e.g., > 0.5 for cosine/L2 depending on Chroma defaults).
4. **Configuration Updates (`src/kb_agent/config.py` & `.env`)**:
   - Expose the new `vector_score_threshold` setting in `config.py` with a default of `0.5`, to be loaded from `kb-agent.json` or `.env`. Note: `vector_score_threshold` is actually already present in `config.py`, we just need to use it in `vector_search.py` and set a default if None.
5. **Adjust Chunk Size (`src/kb_agent/chunking.py`)**:
   - Change the default `max_chars` parameter from `4000` to `800` (and `overlap_chars` from 800 to ~200) to improve retrieval precision.

## Capabilities

### New Capabilities
- `vector-search-threshold`: Adding configurable threshold gating logic to vector search.

### Modified Capabilities
- `query-engine`: Changing the context injection format and history filtering mechanism to prevent bypass bugs and hallucinations.

## Impact

- `kb_agent.agent.nodes`: `tool_node` context appending, `_history_to_messages` filtering.
- `kb_agent.tools.vector_tool`: Distance filtering logic added to `search()`.
- `kb_agent.chunking`: Adjusted default chunking sizes.
- `kb_agent.config`: Utilizing `vector_score_threshold` default value.
