# AGENTS.md

## Entry Points

- `kb-agent` - TUI interface (Textual)
- `kb-cli` - CLI agent for automated tasks
- `python -m pytest tests/ -v` - Run all tests

## Commands

```bash
kb-agent index         # Index documents from data_folder/source
kb-agent               # Launch TUI
kb-cli                 # Launch CLI agent
./scripts/llm_server.sh start  # Start local LLM server (GGUF models)
```

## Configuration

Copy `.env.example` to `.env` and configure:
- `KB_AGENT_LLM_API_KEY` - Required
- `KB_AGENT_LLM_BASE_URL` - API endpoint (default: OpenAI)
- `KB_AGENT_LLM_MODEL` - Model name
- `KB_AGENT_DATA_FOLDER` - Data storage (default: ~/data/kb-agent)

## Project Structure

```
src/kb_agent/
├── cli.py           # Entry: kb-agent index/tui commands
├── skill_cli.py     # Entry: kb-cli
├── tui.py          # Textual TUI interface
├── engine.py       # Public API (KB mode / Chat mode)
├── agent/         # LangGraph CRAG nodes
├── skill/          # CLI skill execution (planner, executor, router)
├── connectors/    # Jira, Confluence, Web, Local file
├── tools/          # vector_tool, file_tool, csv_qa_tool, grep_tool
└── graph/         # NetworkX knowledge graph
```

## Testing

```bash
python -m pytest tests/ -v              # All tests
python -m pytest tests/test_agent_graph.py -v  # Specific test file
```

## OpenSpec Workflows

Uses `.agent/workflows/` and `.agent/skills/` for change management:
- Changes tracked in `openspec/changes/`
- Custom skills in `.agent/skills/`

## Key Constraints

- Anti-hallucination: Agent must only answer from retrieved context or conversation history
- No-Evidence Refusal: If no evidence found, reply "I couldn't find relevant information..."
- Security: PII masking enabled, audit logging to `audit.log`