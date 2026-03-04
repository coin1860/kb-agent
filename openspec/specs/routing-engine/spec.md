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
The system SHALL use an iterative LangGraph-based workflow ("knowledge_base" mode) with a self-adaptive topology that includes conditional edges for fast-path routing based on query complexity, replacing the previous fixed-path 6-node flow. The `tool_node` MUST encapsulate JSON array results from tools like `vector_search` into individual context items rather than a single merged string, ensuring the `grade_evidence_node` correctly evaluates each chunk. For queries explicitly requesting analysis, reading, or querying of a `.csv` file, the `analyze_and_route` node MUST bypass vector search decomposition and output a `"direct"` action to invoke the `csv_query` tool with the extracted filename and user question.

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

#### Scenario: Direct routing for CSV queries
- **WHEN** the user explicitly asks to query, analyze, or read a `.csv` file (e.g., "query dataset.csv for users over 30")
- **THEN** the `analyze_and_route` node MUST classify the action as `"direct"`
- **AND** route to the `csv_query` tool, extracting the filename and the specific question without decomposing into vector search queries

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

### Requirement: Disable Automatic Ingestion on Query
When a URL is detected in a user query, the system shall fetch and use the content to answer the question, but shall not save or index the content into the permanent knowledge base automatically.

#### Scenario: User pastes a URL and asks a question
- **WHEN** the user provided query contains one or more URLs
- **AND** the system is in Knowledge Base (RAG) mode
- **THEN** the system shall fetch the URL content
- **AND** use the content to generate an answer
- **AND** DO NOT call the indexing processor to store the content in Chroma DB or the files database.

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

