## Why

Based on the recent onboarding exploration, the `kb-agent` project currently lacks formal behavioral specifications. As the system grows to include hybrid search (vector + graph) and agentic RAG paths, it is critical to establish a documented baseline of existing capabilities. This change introduces the foundational specs for the system's core indexing and query engine flows without altering any actual code.

## What Changes

- Introduces a formal OpenSpec proposal outlining the existing system baseline.
- Documents the architecture decisions in a new design artifact.
- Creates baseline BDD-style specifications for the indexer and agentic query engine.
- No application code will be modified; this is purely a documentation and specification effort.

## Capabilities

### New Capabilities

- `indexing-pipeline`: Defines the behavior of fetching documents, generating summaries via LLMs, vectorizing content, and building the knowledge graph.
- `query-engine`: Defines the flow for answering user queries, including direct URL fetching, normal LLM chat mode, and the agentic RAG workflow leveraging LangGraph.
- `security-masking`: Describes the system's mechanism for intercepting and masking sensitive information (e.g., credit card numbers) before presenting answers to the user.

### Modified Capabilities

- 

## Impact

- **Documentation**: Establishes `/openspec` as the source of truth for system behavior.
- **Future Development**: Provides a clear boundary and testable acceptance criteria for future modifications to the engine or connectors.
- **Codebase**: No source files (`src/kb_agent/*`) will be affected. All changes are confined to the `openspec/changes/system-baseline-docs` directory.
