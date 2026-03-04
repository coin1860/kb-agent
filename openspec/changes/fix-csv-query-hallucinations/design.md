## Context

The current `csv_query` tool is frequently failing because the Agent is trying to guess the column headers based solely on the user request, leading to Pandas query syntax errors or "column not found" errors. When these errors occur, the tool only returns the exception trace, which does not provide the agent with the valid headers. This leads to a loop of repeated failures (hallucinations).

## Goals / Non-Goals

**Goals:**
- Eliminate column name hallucinations when querying CSV files.
- Provide a recovery mechanism when the agent inevitably writes a bad pandas query.
- Make the process transparent and testable without degrading user experience.

**Non-Goals:**
- Supporting arbitrary Python execution (we stick strictly to Pandas query engine).
- Changing how the data files are loaded or searched on disk.

## Decisions

1. **Expose `get_csv_schema_and_sample` as a Tool in `tools.py`**:
   **Rationale**: By formally defining a `csv_info` tool that wraps this existing function, the Agent can "look before it leaps." The `csv_query` tool's system prompt will include a `CRITICAL INSTRUCTION` demanding that the Agent call `csv_info` first before running a query, ensuring it has ground-truth headers in its context.

2. **Self-Correction Loop via Error Metadata**:
   **Rationale**: If the agent still writes a bad query, simply returning "Error: Column X not found" isn't helpful enough. Instead, we intercept the exception, read `list(df.columns)`, and inject a rich error string: `"[Error]... Valid columns: [...]. Please correct your pandas query strictly using ONLY these headers and try again."` This gives the agent the explicit "cheat sheet" it needs to auto-correct in the LangGraph loop.

## Risks / Trade-offs

- **Risk**: The Agent refuses to use `csv_info` and goes straight to `csv_query` despite the prompt instruction.
  **Mitigation**: The rich error return combined with LangGraph's Re-Act loop will catch the agent on the first failure. The first failure's error will supply the schema, meaning worst-case scenario is one wasted LLM call before successful completion.
