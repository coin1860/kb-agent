## Why

The current Knowledge Base Agent provides dense vector retrieval and direct knowledge graph traversal. However, users frequently need an exact-match semantic file search and explicit document-based Q&A (e.g., "Find the Mexico payment files and summarize them"). This change introduces a dedicated `Local File QA Tool` that can query the index structure for filename/context matches, return structured tables, and restrict subsequent Q&A strictly to those retrieved reference tables.

## What Changes

- Create a new `LocalFileQATool` that can perform semantic keyword searches against the filename and truncated content indexing metadata.
- Enhance the `Engine` (`Agentic RAG` workflow) to interpret user instructions like "Find files related to X" and utilize the new tool.
- Enforce a specific formatted output from the Agent when presenting found files (Index + Filename).
- Enable restricted Q&A where a user can say "Summarize file 1", and the agent selectively retrieves from `KB_AGENT_DATA_FOLDER/index/<md_name>` using that table index.

## Capabilities

### New Capabilities
- `local-file-qa-tool`: A new LangChain/LangGraph-compatible tool to perform explicit filename and context matching, and outputting the top 5 matches in a structured table format.

### Modified Capabilities
- `query-engine`: Update the agentic RAG workflow to trigger the local file QA behaviors and manage conversational state containing the file index references.

## Impact

- Adds `kb_agent/tools/local_file_qa.py` (or integrates into existing file/vector tools).
- Modifies `kb_agent/engine.py` or `kb_agent/agent/nodes.py` to prompt the LLM to format the response into the 1-indexed table list.
- Minimal dependency impact. Relies heavily on the existing ChromaDB `metadata.type == 'summary' or 'full'` architecture.
