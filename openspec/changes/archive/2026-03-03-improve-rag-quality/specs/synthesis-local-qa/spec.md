---
title: Local File QA Tool
domain: synthesis
---

## REMOVED Requirements

### Requirement: Search local files by keywords
**Reason**: `local_file_qa` is functionally redundant with `vector_search` — both use the same ChromaDB collection and embedding. The tool causes LLM confusion by providing a second search interface that returns only filenames instead of content. `vector_search` already returns `metadata.related_file` which provides the same file path information.
**Migration**: Use `vector_search` for all search queries. File paths are available in the `metadata.related_file` field of vector_search results.

### Requirement: Format search results as 1-indexed table
**Reason**: Removed along with the parent `local_file_qa` tool. File listing can be achieved by instructing the synthesize prompt to format vector_search file paths as a numbered list when the user intent is file discovery.
**Migration**: The synthesize prompt already handles file list formatting when context contains file path metadata.
