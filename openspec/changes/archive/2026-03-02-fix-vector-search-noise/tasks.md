## 1. Context Encapsulation Bug Fix

- [x] 1.1 Update `kb_agent.agent.nodes.tool_node` to check if `parsed_res` from tools like `vector_search` is a list, and if so, append each item format as a separate string to `new_context` instead of joining them into one.

## 2. LLM Usage Stats Hallucination Fix

- [x] 2.1 Update `kb_agent.agent.nodes._history_to_messages` to strip out appended `LLM Usage Stats` text from the `content` of `assistant` messages before returning the LangChain message objects, preventing the LLM from mimicking the stats.

## 3. Vector Score Threshold

- [x] 3.1 Update `kb_agent.config.Settings` to ensure `vector_score_threshold` uses the default `0.5` if none is provided.
- [x] 3.2 Update `kb_agent.tools.vector_tool.VectorTool.search` to accept a `threshold` argument (defaulting to config value).
- [x] 3.3 Update `VectorTool.search` logic to filter out raw results from ChromaDB whose distance metric is greater than the configured threshold (for L2 distance; assuming default Chroma L2 metric).

## 4. Chunk Sizing Optimization

- [x] 4.1 Update `kb_agent.chunking.split_by_paragraphs` default signature: `max_chars: int = 800, overlap_chars: int = 200`.
- [x] 4.2 Update `kb_agent.chunking.MarkdownAwareChunker.__init__` default signature: `max_chars: int = 800, overlap_chars: int = 200`.
- [x] 4.3 Ensure no regressions in indexing tests.

## 5. Verification
- [x] 5.1 Run all tests locally (`pytest`) to ensure `tool_node` and vector tool modifications don't break existing tests.
- [x] 5.2 Validate vector search on a test file to ensure low-relevance chunks are filtered out.
