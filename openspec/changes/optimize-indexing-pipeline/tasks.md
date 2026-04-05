## 1. Indexing Pipeline Optimizations

- [x] 1.1 Update `kb_agent.processor.Processor` to skip writing `.md` disk duplicates when indexing if processing directly from memory strings is possible.
- [x] 1.2 Modify `kb_agent.processor.Processor` to conditionally call the LLM for summary generation only if the source `full_content` length is strictly greater than 2000 characters.
- [x] 1.3 Refactor `Processor.process` to stop creating an independent `{doc_id}-summary` index entry within ChromaDB vector store.

## 2. Chunk Enrichment

- [x] 2.1 Update `kb_agent.chunking.MarkdownAwareChunker` to prepend template contextual prefixes (`Document: X\nSection: Y\nSummary: Z\n\n`) to the `chunk.text` property for all split chunks.
- [x] 2.2 Ensure the Prefix formatting grace-handles any absence of a summary (e.g. if skipped due to length constraints).
- [x] 2.3 Verify embeddings execute over the successfully expanded `chunk.text` within `kb_agent.processor.Processor`.
