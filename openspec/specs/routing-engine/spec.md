---
title: Query Engine
domain: routing
---

# query-engine Specification

## Purpose
TBD - created by archiving change system-baseline-docs. Update Purpose after archive.
## Requirements
### Requirement: Answer queries via Normal chat mode
The system SHALL support a standard conversational mode ("normal") that directly streams user input to the LLM without augmenting it via the agentic workflow.

#### Scenario: User queries the engine in normal mode
- **WHEN** the `Engine.answer_query` is called with `mode="normal"`
- **THEN** the system bypasses the retrieval pipeline
- **AND** the system returns a direct LLM response using the provided chat history

### Requirement: Answer queries via Agentic RAG
The system SHALL use an iterative LangGraph-based workflow ("knowledge_base" mode) with a self-adaptive topology that includes conditional edges for fast-path routing based on query complexity, replacing the previous fixed-path 6-node flow. The `tool_node` MUST encapsulate JSON array results from tools like `vector_search` into individual context items rather than a single merged string, ensuring the `grade_evidence_node` correctly evaluates each chunk.

#### Scenario: Chitchat query fast-path
- **WHEN** the user submits a query and `mode="knowledge_base"` and `analyze_and_route` classifies complexity as `"chitchat"`
- **THEN** the Engine routes directly to `synthesize`, bypassing `plan`, `tool_exec`, and `grade_evidence`
- **AND** the total LLM calls for this query is 2 (analyze + synthesize)

#### Scenario: Simple query fast-path
- **WHEN** the user submits a query and `mode="knowledge_base"` and `analyze_and_route` classifies complexity as `"simple"`
- **THEN** the Engine routes through `plan → tool_exec → synthesize`, bypassing `grade_evidence`
- **AND** the total LLM calls for this query is 3 (analyze + plan + synthesize)

#### Scenario: Complex query full pipeline
- **WHEN** the user submits a query and `mode="knowledge_base"` and `analyze_and_route` classifies complexity as `"complex"` or classification is unavailable
- **THEN** the Engine invokes the full pipeline: `analyze_and_route → plan → tool_exec → grade_evidence → synthesize`
- **AND** the `grade_evidence` node scores retrieved evidence and decides GENERATE, REFINE, or RE-RETRIEVE

#### Scenario: User queries a technical term requiring context
- **WHEN** the user submits a query and `mode="knowledge_base"`
- **THEN** the Engine invokes the compiled LangGraph workflow
- **AND** the workflow first analyzes query intent and complexity via `analyze_and_route`
- **AND** the workflow executes adaptive tool calls based on the routing plan
- **AND** the engine ultimately returns a synthesized answer with source citations

#### Scenario: Plan node respects routing plan in fallback paths
- **WHEN** the `plan_node` LLM response fails JSON parsing and falls back to text extraction
- **THEN** the system SHALL only extract tools that are present in `routing_plan.suggested_tools`
- **AND** the system SHALL validate each tool's applicability to the query before including it
- **AND** the system SHALL NOT call `jira_fetch`, `confluence_fetch`, or `web_fetch` unless the query contains a valid tool-specific argument pattern

#### Scenario: Vector search returns multiple chunks
- **WHEN** the `tool_node` executes `vector_search` which returns 5 chunks
- **THEN** the `tool_node` appends 5 distinct formatted items to `new_context`
- **AND** the `grade_evidence_node` receives all 5 items and properly triggers the LLM grading (since 5 > auto_approve_max_items).

### Requirement: Generate answers with source citations and LLM stats
The system SHALL include source citations in the synthesized answer, referencing the file path and line number of each piece of evidence used, and SHALL append a final formatted block containing aggregated LLM usage statistics (API calls and total tokens) accumulated from the `AgentState`. The system MUST ensure that these statistics are only appended once by filtering out any hallucinated or previously appended stats blocks from the conversation history before it is passed to the LLM.

#### Scenario: Answer with inline citations and LLM stats
- **WHEN** the `synthesize` node generates an answer from graded evidence
- **THEN** the answer includes numbered footnote references inline (e.g., `[1]`, `[2]`)
- **AND** a citation footer is appended listing each source: `[N] /path/to/file.md:L42`
- **AND** a new line reading `---` followed by a `📊 **LLM Usage Stats:**` block containing token/latency breakdown is appended at the very end of the response

#### Scenario: Evidence without line number metadata
- **WHEN** a context item comes from `vector_search` and lacks a specific line number
- **THEN** the citation references only the file path without line number (e.g., `[N] /path/to/file.md`)

#### Scenario: No evidence available for synthesis
- **WHEN** the `synthesize` node has no context items (all filtered or empty)
- **THEN** the system responds with "I couldn't find relevant information in the knowledge base to answer this question."
- **AND** no citation footer is appended
- **AND** the `📊 **LLM Usage Stats:**` block IS STILL appended to show the cost of processing the unanswerable query

#### Scenario: LLM hallucinates previous stats
- **WHEN** the synthesized answer is being prepared and the conversation history contains previous LLM Usage Stats blocks
- **THEN** the system filters them out from the prompt
- **AND** the final answer contains only exactly one correct `LLM Usage Stats` block appended by the system.

### Requirement: Automatic web URL resolution
The system SHALL intercept HTTP URLs in user queries, fetch their content, and use it as ad-hoc context to answer the user's question, bypassing the standard RAG or local index database. When fetching raw HTML, the system must robustly filter out non-content elements without inadvertently destroying the main article container itself.

#### Scenario: Query contains a URL
- **WHEN** the user provides the query "Summarize this page https://example.com/spec"
- **THEN** the system detects the URL via regex
- **AND** the system fetches the web content
- **AND** the system optionally processes it into the index if in knowledge_base mode
- **AND** the system answers the user's implicit or explicit question using only that fetched content

#### Scenario: Aggressive Layouts (e.g., GitHub Repos)
- **WHEN** the `web_connector` (via `markdownify` engine) processes a page with layout parent classes containing "sidebar" or "banner"
- **THEN** the system SHALL extract the localized `main_content` node based on tag heuristics (`<article>`, `<main>`, etc.) first
- **AND** apply CSS-selector-based destructive filtering (e.g. `[class*='sidebar']`) ONLY to the descendants inside this localized subtree
- **AND** preserve the top-level main/article wrapper content itself 
- **AND** successfully convert the rich content to Markdown without truncation

### Requirement: Contextual File Q&A
The planner agent SHALL be able to explicitly resolve an index number (e.g., "1") to a specific filename when the user asks a follow-up question based on the `LocalFileQATool`'s table output.

#### Scenario: User asks to summarize file 1
- **WHEN** the user says "Summarize file 1"
- **AND** the conversation history contains a `LocalFileQATool` result table
- **THEN** the planner agent looks up the filename corresponding to index `1`
- **AND** the planner agent calls the `read_file` tool with that specific filename
- **AND** the synthesizer returns a summary based strictly on that file

