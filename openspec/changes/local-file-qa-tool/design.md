## Context

The current `kb-agent` system relies on `VectorTool` and `GrepTool` for implicit context retrieval. Users type a query, and the LangGraph Engine decides which tool to use. However, when users want to *explicitly interact with specific files* (e.g., "Find the Mexico payment files and summarize file 1"), the current system struggles because:
1. It doesn't present an interactive, numbered list of files.
2. It lacks a tool strictly optimized for semantic filename+snippet matching in isolation.

This design introduces a `LocalFileQATool` and a structured output protocol to solve this constraint.

## Goals / Non-Goals

**Goals:**
- Provide a reliable way for users to search for local Markdown files by name and content.
- Present search results in a strictly formatted enumerated list (Table/List format).
- Allow the RAG engine to "target" specific files based on their index number in subsequent turns.

**Non-Goals:**
- Replacing `VectorTool` for general open-ended knowledge queries.
- Building a new database. We will reuse ChromaDB.

## Decisions

### 1. Reusing ChromaDB Metadata
- **Decision:** The `LocalFileQATool` will query the existing `kb_docs` ChromaDB collection but will filter strictly for `type: "summary"` or `type: "full"` to extract the exact `related_file` (the markdown filename).
- **Rationale:** No need to build a secondary SQLite or inverted index for filenames. ChromaDB's semantic embedder can handle "Mexico payments" and match both the file name (via metadata/content) and the generated summary.

### 2. Formatted Output Protocol (The "1-Indexed List")
- **Decision:** The agent's `synthesize_node` (or the tool itself) will be strictly prompted to return file matches in the format requested by the user:
  ```
  1, file name1 (filename match)
  2, file name2 (context match)
  ```
- **Rationale:** This creates a strict contract between the user and the agent. The state (`AgentState["messages"]`) will retain this list, allowing the user's next message ("summarize file 1") to be perfectly resolved by the LLM by looking back at the chat history.

### 3. "Rag Mode Only" Trigger
- **Decision:** This feature is exclusive to the Agentic RAG mode (`mode="knowledge_base"`).
- **Rationale:** Normal mode is a stateless direct LLM pass-through. It has no access to `VectorTool` or the local filesystem index.

## Risks / Trade-offs

- **[Risk: Context Window Confusion on "File 1"]** → If the conversation gets long, the LLM might forget which file "File 1" refers to.
  - *Mitigation:* The prompt for `plan_node` must aggressively instruct the LLM to resolve index numbers (e.g., "1") to actual filenames (`file name1`) from the immediate chat history before issuing the `read_file(file_path)` tool call.
- **[Risk: Filename vs Context Match Classification]** → ChromaDB doesn't natively tell us if it matched just the filename or the text body.
  - *Mitigation:* We can simulate this classification by checking if the query words appear in the `metadata["related_file"]` string. If yes → `(filename match)`, else → `(context match)`.
