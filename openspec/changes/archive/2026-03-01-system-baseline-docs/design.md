## Context

The `kb-agent` project implements a hybrid search architecture for local knowledge bases, combining dense vector embeddings (ChromaDB) with a semantic Knowledge Graph (NetworkX). It exposes its functionality both through a traditional CLI (`kb-agent index`) and a rich Textual-based terminal UI (`kb-agent tui`). 

As the project scales to incorporate an agentic RAG workflow using LangGraph, it is essential to formally document the existing baseline architecture and design decisions that govern the indexing pipeline and query engine. This document serves as the architectural reference for the baseline system capabilities defined in the proposal.

## Goals / Non-Goals

**Goals:**
- Document the local-first architectural choices of `kb-agent`.
- Explain how dense vectors and the knowledge graph complement each other in the indexing pipeline.
- Detail the multi-modal routing logic in the query engine (direct fetching vs. direct LLM vs. Agentic RAG).
- Serve as the baseline for future architectural modifications.

**Non-Goals:**
- Proposing new features or refactoring existing code.
- Detailed, line-by-line code explanations (those belong in the codebase or focused technical specs).
- Documenting deployment or CI/CD pipelines.

## Decisions

### 1. Hybrid Storage Engine (Vector + Graph)
- **Decision:** Use ChromaDB for dense document embeddings and NetworkX for the Knowledge Graph.
- **Rationale:** Traditional RAG relies solely on semantic similarity, which fails when answering multi-hop questions (e.g., "What is the status of the Jira ticket blocking the feature mentioned in this doc?"). By parsing markdown links and Jira tags to build a directed graph (NetworkX), the agent can traverse explicit entity relationships that dense vectors might miss.

### 2. File-Based State and Configuration
- **Decision:** Use local `.env` files for configuration and `~/.kb-agent/` (or local `docs/`, `archive/`, `index/` directories) for state.
- **Rationale:** Prioritizes developer experience and ease of local setup. It avoids the overhead of managing a centralized database for application state, aligning with the tool's nature as a local knowledge assistant.

### 3. Agentic RAG via LangGraph
- **Decision:** Implement the primary "Knowledge Base" query mode using a LangGraph-based state machine.
- **Rationale:** Rather than a single prompt-and-fetch cycle, LangGraph allows the agent to iteratively assess whether it has gathered "sufficient" information using its available tools (`VectorTool`, `GraphTool`, `GrepTool`). This dynamic tool-use loop significantly improves answer accuracy for complex queries.

### 4. Asynchronous Tool Execution in TUI
- **Decision:** The `kb-agent tui` uses textual's asynchronous workers to handle long-running LLM and indexing tasks.
- **Rationale:** Prevents the terminal UI from freezing during network calls to OpenAI/Groq or heavy local embedding computations.

## Risks / Trade-offs

- **[Risk: Local File Parsing Fragility]** → The `GraphBuilder` relies on regex to extract Jira tickets and Markdown links. Changes in documentation markup styles could break graph connectivity.
  - *Mitigation:* Comprehensive unit tests for `GraphBuilder` regex matching across various markdown flavors.
- **[Risk: Agentic Loop Exhaustion]** → The LangGraph agent might get stuck in an infinite loop if it cannot find the required information.
  - *Mitigation:* Implement strict iteration limits (e.g., `MAX_ITERATIONS`) within the LangGraph state definition to force a terminal state.
- **[Risk: Large Graph Memory Consumption]** → NetworkX stores the entire graph in RAM. For extremely large knowledge bases, this could cause memory issues.
  - *Mitigation:* For V1, local docbases are assumed to be reasonably sized. Future iterations may require migrating to a persistent graph database (like Neo4j) if memory becomes a bottleneck.
