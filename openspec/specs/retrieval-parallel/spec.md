---
title: Parallel Retrieval
domain: retrieval
---

# parallel-retrieval Specification

## Purpose
TBD - Add parallel tool retrieval and simplify main RAG routing flow.

## Requirements

### Requirement: Parallel Retrieval Orchestration
The planning node must be capable of orchestrating multiple retrieval tools in a single execution step to gather comprehensive evidence, rather than relying on a monolithic hybrid search function.

#### Scenario: Complex Query Requiring Both Exact and Semantic Search
- **WHEN** the user asks a complex query that contains both recognizable exact entities (like specific tool names or module names) and a broader semantic question (e.g., "what is the architecture of the VectorTool?")
- **THEN** the planning node emits a parallel tool execution plan containing both a `grep_search` call (for the exact entity) and a `vector_search` call (for the semantic concept)
- **AND** the execution node runs both tools
- **AND** all resulting chunks from both tools are appended to the context for the `grade_evidence` node to evaluate.

### Requirement: Direct Flow Control
The RAG pipeline must proceed directly from initialization/state creation to the planning phase, removing intermediate intent-classification nodes that enforce strict structured output prerequisites.

#### Scenario: Processing a Standard RAG Query
- **WHEN** a standard RAG query is received by the agent
- **THEN** the graph execution proceeds from `START` directly to `plan_node` (or an equivalent lightweight gateway that primarily defers to `plan_node`).
- **AND** the `plan_node` receives the raw user query without requiring pre-processed intent dictionaries or keyword lists.
