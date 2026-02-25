# KB Agent (Bank Agent)

A secure, enterprise-grade AI Agent for internal bank document retrieval.

## Features

- **Hybrid Search**: Combines `ripgrep` (exact match) and `ChromaDB` (semantic search).
- **Agentic Reasoning**: Automatically decides whether to read document summaries or full content based on query complexity.
- **Security**: Masks sensitive data (credit card numbers) in outputs. Local-first design.
- **TUI**: Terminal User Interface built with Textual for easy interaction.
- **Connectors**: Supports local Markdown files (and extensible to Jira/Confluence).

## Installation

This tool is designed to be installed via `pip`.

```bash
# Clone the repository
git clone <repo_url>
cd kb-agent

# Install dependencies and the tool
pip install .
```

## Configuration

The agent requires an LLM provider (OpenAI-compatible). You can configure it via environment variables or the TUI Settings screen.

### Environment Variables

Create a `.env` file in your working directory or export these variables:

```bash
export KB_AGENT_LLM_API_KEY="sk-..."
export KB_AGENT_LLM_BASE_URL="https://api.openai.com/v1"
export KB_AGENT_LLM_MODEL="gpt-4"
export KB_AGENT_DOCS_PATH="~/data/markdown_docs"
```

- `KB_AGENT_DOCS_PATH`: Directory containing your Markdown documents. Defaults to `~/data/markdown_docs`.

### Runtime Configuration

When you launch `kb-agent` for the first time, if no configuration is found, a Settings screen will appear asking for your API Key and Base URL.

## Usage

### 1. Interactive Mode (TUI)

Launch the agent interface:

```bash
kb-agent
```

- **Type your question** in the input box at the bottom.
- **View logs** on the right panel to see what the agent is thinking (Searching, Reading, etc.).
- **Read answers** in the main viewer.

### 2. Indexing Documents

To update the search index (ChromaDB) with new documents:

```bash
kb-agent index
```

This scans the `KB_AGENT_DOCS_PATH` for Markdown files, generates summaries using the LLM, and indexes them.

## Directory Structure

- `src/kb_agent`: Source code.
  - `cli.py`: Entry point.
  - `tui.py`: Textual UI.
  - `engine.py`: Core logic.
  - `processor.py`: Data processing and indexing.
  - `tools/`: Grep, Vector, File tools.
  - `connectors/`: Data fetchers.
- `audit.log`: Audit trail of all queries and agent actions.

## Development

Run tests:

```bash
python3 -m pytest tests/
```

## Security Note

All output is passed through a masking filter to hide potential 16-digit credit card numbers.
Audit logs are stored locally.
