## Why
The user wants a convenient `/index` slash command to automatically index external resources (like URLs, Jira tickets, Confluence pages) directly from the chat interface. Currently, external resources or files are handled by checking existing tools, but adding an explicit command streamlines the experience. The command will improve the UX by integrating the indexing workflow natively into the chat interactions.

## What Changes
- Add a new `/index <url_or_ID>` slash command.
- Upon receiving the command, the AI will automatically identify the appropriate tool/parser based on the provided URL, Jira ticket, or Confluence link to parse the content.
- After fetching and converting the source to Markdown, it will execute the remainder of the existing `kb-agent index` logic:
  - Save the parsed `.md` file to the `index` folder.
  - Archive the original source in the `archive` folder.
  - Process and split the document, storing the chunks into Chroma DB.
*(Note: The underlying tools for pulling the data and injecting it into the Vector DB are largely implemented; this change wires them to the `/index` command and orchestrates the existing document saving/archiving logic.)*

## Capabilities

### New Capabilities
- `index-command`: Introduces the `/index` chat command that coordinates fetching external content (Jira, Confluence, web pages), parsing it to Markdown, saving/archiving it, and storing chunked data in Chroma DB.

### Modified Capabilities

## Impact
- **Agent Entrypoints/Nodes**: Needs to detect and parse the `/index` command from user input.
- **Workflow / Tools**: Needs to sequence the extraction tool, save the resulting Markdown file to `index/`, move any source context to `archive/`, and trigger the Chroma DB ingestion for the new file.
