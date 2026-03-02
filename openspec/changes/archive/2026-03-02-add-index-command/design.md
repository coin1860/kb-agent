## Context
Users currently interact with the Knowledge Base by putting files in the source directory and running `kb-agent index`, or by letting the system fetch URLs dynamically during chat queries (via `_handle_urls`).
To streamline adding external resources (URLs, Jira tickets, Confluence) explicitly into the persistent vector database directly from the TUI, the user requested an explicit `/index <target>` slash command.

## Goals / Non-Goals

**Goals:**
- Provide a responsive `/index <url | jira_id | confluence_id>` command in the TUI.
- Automatically route the target to the correct data connector (`WebConnector`, `JiraConnector`, or `ConfluenceConnector`).
- Retrieve the content, convert it to Markdown, and orchestrate the ingestion:
  - Save the `.md` content to the `index` folder.
  - Store the vector chunks via `Processor.process(...)` (ChromaDB).
  - Provide clear UI feedback (success/failure) in the TUI log.

**Non-Goals:**
- Modifying the core `kb-agent index` CLI process for local files.
- Modifying or rewriting existing connectors (they already fetch/convert to Markdown).

## Decisions

1. **Routing in TUI:**
   - Modify `SLASH_COMMANDS` in `tui.py` to include `/index`.
   - Update `_exec_slash` to handle commands with arguments (e.g., splitting by space).
2. **Implementation Location: Engine:**
   - Introduce an `index_resource(target: str, status_callback)` method inside `src/kb_agent/engine.py`. This keeps the TUI lean and integrates well with the existing `Processor` and `Config` states already available in the `Engine`.
3. **Auto-Detection Logic:**
   - URL: Matches `http://` or `https://` prefix -> `WebConnector`.
   - Jira: Matches `[A-Z]+-\d+` regex -> `JiraConnector`.
   - Confluence: Matches digit strings (Page ID) or explicit Confluence URL -> `ConfluenceConnector`.
4. **Archiving Strategy:**
   - The user mentioned "source file to archive". For web/Jira resources, there is no local "source file" to move as there is with local PDFs/DOCXs. We will save the generated `.md` file directly to `settings.index_path`. Moving a source file is skipped for these purely remote resources, which aligns with how connectors currently work (returning in-memory dictionaries).

## Risks / Trade-offs

- **Risk:** Confluence vs. Jira ambiguity. A user might paste a Confluence page ID that looks like a normal number, or a Jira ticket.
  *Mitigation:* Use strict regex for Jira (`^[A-Z]+-\d+$`). Fallback to Confluence if it's just numbers (`^\d+$`), and Web if it's a URL.
- **Risk:** Blocking the TUI thread.
  *Mitigation:* The command should be executed using the existing async `work` mechanisms in the TUI (like how normal chats are processed) so the UI doesn't freeze during web fetches.
