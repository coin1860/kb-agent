## Context

In `kb_agent/engine.py`, the `_handle_urls` method handles URL detection in user queries. Currently, it has a conditional block that checks if the mode is `knowledge_base`. If so, it initializes a `Processor` and calls `processor.process(doc)`, which triggers:
- Saving the markdown to `docs/`
- Generating a summary
- Ingesting into the vector store

This behavior happens automatically when a URL is found in a query, even if the user just wanted to ask a question about the page.

## Goals / Non-Goals

**Goals:**
- Remove the automatic indexing/processing step from the query path in `KB Agent`.
- Ensure that URLs pasted into the chat are only used as temporary context for the current conversation.
- Maintain the `/index <URL>` command as the primary way to explicitly index web content.

**Non-Goals:**
- Removing the ability to fetch web content during a query (fetching is still required to answer questions about the URL).
- Modifying the indexing logic itself (the `index_resource` method and `Processor` should remain unchanged).

## Decisions

### 1. Remove processing from `_handle_urls`
We will delete the `if mode == "knowledge_base":` block inside `_handle_urls` in `kb_agent/engine.py`.

**Rationale:** This fulfills the user requirement to stop automatic indexing. The `all_content.append(...)` call that follows will still ensure the content is available for the LLM to answer the immediate question.

### 2. Rely on Explicit Indexing
Users who want content indexed must use the `/index` command or the CLI `kb-agent index`.

**Rationale:** This provides clearer separation of concerns between "searching/asking" and "building the knowledge base".

## Risks / Trade-offs

**Risks:**
- Users who were used to automatic indexing might be confused if their query history doesn't automatically become part of the knowledge base. However, the presence of the `/index` command and the user's explicit request for this change mitigate this.

**Trade-offs:**
- Slightly more manual work for users who *do* want to index every URL they talk about, but results in a much cleaner and more intentional knowledge base.
