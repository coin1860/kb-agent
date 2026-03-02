## 1. Engine Core Updates

- [x] 1.1 Add `index_resource(url_or_id: str, on_status=None)` method to `Engine`.
- [x] 1.2 Implement regex matching in `index_resource` to route to Web, Jira, or Confluence connectors.
- [x] 1.3 Implement the fetch, markdown conversion, and ChromaDB ingestion pipeline in `index_resource()`.
- [x] 1.4 Handle saving the converted `.md` file to the `settings.index_path`.
- [x] 1.5 Add robust error handling in `index_resource` (e.g., fetch failures, parsing errors).

## 2. TUI Slash Command Integration

- [x] 2.1 Add `/index` to `SLASH_COMMANDS` list in `kb_agent/tui.py`.
- [x] 2.2 Update `_exec_slash` in `KBAgentApp` to parse the `/index` command and its argument.
- [x] 2.3 Wire the parsed `/index <target>` command to call `self.engine.index_resource()` asynchronously via a Textual `@work` worker.
- [x] 2.4 Update the UI log with a success or error message based on the result of `index_resource()`.

## 3. Testing and Verification

- [x] 3.1 Verify `/index <url>` fetches the webpage, chunks it into ChromaDB, and saves the `.md` file to `index/`.
- [x] 3.2 Verify `/index <PROJ-ID>` correctly routes to the Jira connector and ingests the ticket.
- [x] 3.3 Verify `/index <PAGE-ID>` correctly routes to the Confluence connector and ingests the page.
- [x] 3.4 Ensure invalid URLs or missing arguments display appropriate error messages without crashing the TUI.
