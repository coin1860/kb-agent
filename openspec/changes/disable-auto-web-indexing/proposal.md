## Why

Currently, when a URL is pasted into the TUI in Knowledge Base (RAG) mode, the system automatically fetches the content, generates a summary using an LLM, and indexes it into the Chroma database. While useful for building a library, this behavior is often redundant since a dedicated `/index` command already exists for this purpose. 

Users frequently want to simply discuss or analyze a specific web page without permanently adding it to their knowledge base. Automatically indexing every URL consumes LLM tokens (for summaries) and database space unnecessarily, and can lead to a cluttered index.

## What Changes

The automatic indexing behavior in the KB RAG mode will be disabled. When a URL is detected in the user query:
1. The engine will still fetch the content and convert it to Markdown.
2. The fetched content will be used as temporary context for the immediate query answer.
3. The system will **NOT** call the Processor to generate a summary or ingest the content into Chroma DB.

This aligns the URL handling behavior of the Knowledge Base mode with the existing Normal (Chat) mode, where URLs are treated as temporary query context.

## Capabilities

### New Capabilities
- None

### Modified Capabilities
- None (The core capability of RAG and URL handling remains the same, only the implementation of the high-level workflow is adjusted to remove an automatic step.)

## Impact

- `kb_agent/engine.py`: The `_handle_urls` method will be modified to bypass the processor when in `knowledge_base` mode.
- Users will now need to explicitly use the `/index` command if they want to permanently add a URL's content to their knowledge base.
