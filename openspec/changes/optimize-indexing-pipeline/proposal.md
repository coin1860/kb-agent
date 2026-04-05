## Why

The current indexing pipeline is inefficient and results in sub-optimal RAG retrieval. `.md` files are redundantly copied during processing. Furthermore, LLM-generated summaries are indiscriminately created for all documents and indexed as separate embeddings, which often lack precise context and waste LLM tokens. Small markdown chunks resulting from formatting (like short headers or small paragraphs) also lose vital context during indexing, making them difficult for RAG vector search to retrieve accurately. The goal is to optimize both the cost (fewer unnecessary LLM calls) and retrieval precision of the indexing process.

## What Changes

- Skip redundant file writes: Process `.md` documents directly without writing an exact same `.md` copy.
- Remove independent summary embeddings.
- Add Contextual Chunking: Embed contextual information (document title, section title) into each chunk's `content` text so that metadata accompanies the chunk context directly during vector search and retrieval.
- Only generate LLC summaries for longer documents, saving costs on shorter snippets. Note that the generated summary should also be prepended into chunks as context if available.
- **BREAKING**: Re-indexing required. The existing vector index in ChromaDB must be deleted and all files must be re-indexed due to the new indexing format. (The vector structures of existing `-summary` rows will no longer align with the updated retrieval strategy).

## Capabilities

### New Capabilities
- `contextual-chunking`: Ability to inject document context (title, section, summary) into individual content chunks prior to embedding to improve RAG accuracy for small text spans.

### Modified Capabilities
- `data-indexing`: Update the core indexing pipeline behavior to optimize local `.md` file processing and conditional LLM summary generation based on document length.

## Impact

- `kb_agent.processor.Processor`: Will bypass saving redundant `.md` files. Will consolidate index document metadata, removing standalone summary additions to ChromaDB. Will conditionally fetch LLM summaries.
- `kb_agent.chunking.MarkdownAwareChunker`: Will be updated to prepend contextual prefixes to individual chunks.
- Database: Users must purge existing `.chroma` stores to accommodate the new structured embeddings.
