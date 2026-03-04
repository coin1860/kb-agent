## Context

The current system relies on vector search and basic loading for documents. For `.csv` files specifically, simple statistical or textual extraction is often insufficient. Pandas `.query()` offers a robust syntax for filtering and retrieval. However, executing arbitrary code (even just pandas queries) poses a security injection risk if the LLM-generated string isn't sanitized or constrained.

## Goals / Non-Goals

**Goals:**
- Provide a dedicated, safe way to filter, search, and retrieve data from CSV files.
- Integrate the tool into the agent's routing mechanism seamlessly when a user mentions a `.csv` file.
- Prevent memory leaks by caching the loaded CSVs and releasing them when the chat is cleared.

**Non-Goals:**
- Support for complex multi-table joins or extensive analytics operations outside the scope of pandas single Dataframe `.query()`.
- Allowing arbitrary python code execution.

## Decisions

- **Use `pd.query()` subset**: We will instruct the LLM to generate pure JSON containing `condition` and `columns`. This avoids arbitrary `eval()` or `.exec()` calls on open-ended python strings. The python implementation will parse the JSON safely and apply it via `.query()`.
- **Implementation via `csv_qa_tool.py`**: A dedicated single-responsibility tool file ensures we keep `local_file_qa.py` (which handles markdown/PDF RAG) separate.
- **Priority Loading logic**: We'll define a 2-tier search sequence (`archive/` then `source/`) to find the requested file, falling back cleanly if missing.
- **Global Memory Dictionary**: A dictionary `_df_cache` in the tool module will store DataFrames to avoid repeated slow disk reads during a multi-turn conversation.

## Risks / Trade-offs

- **Memory Limit / Cache growth** → Mitigation: Only cache the recently used dataframes, and provide a clear integration in `kb_agent/tui.py`'s `clear_chat` to release references.
- **LLM Syntax Errors** → Mitigation: Use try-except block when executing `df.query(condition)`. If it fails, return the error directly so the LLM can auto-correct in the next turn.
