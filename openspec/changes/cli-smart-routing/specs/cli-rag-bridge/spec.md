## ADDED Requirements

### Requirement: CLI free_agent mode routes through RAG graph
When `route_intent` returns `free_agent` (no skill matched), the CLI SHALL delegate the query to the compiled RAG LangGraph pipeline instead of calling `generate_plan` and `execute_plan`.

#### Scenario: free_agent query handled by RAG graph
- **WHEN** the user submits a query in kb-cli
- **AND** `route_intent()` returns `route="free_agent"` (no skill matched)
- **THEN** `SkillShell._run_rag_query()` SHALL be called with the resolved command and the current session messages
- **AND** the RAG graph SHALL be invoked via `compiled_graph.invoke(initial_state)`
- **AND** the `final_answer` from `AgentState` SHALL be passed to `renderer.print_result()`

#### Scenario: chitchat query answered directly without tools
- **WHEN** the user submits a conversational input (e.g., "hi", "谢谢", "你好")
- **AND** `route_intent()` returns `free_agent`
- **AND** `analyze_and_route` classifies `route_decision="direct"`
- **THEN** the RAG graph MUST skip `plan_node`, `tool_exec`, `grade_evidence`, and `reflect`
- **AND** `synthesize_node` MUST respond using chitchat mode (no evidence required)
- **AND** the user SHALL see a natural language response without any plan table or tool execution steps

#### Scenario: knowledge query goes through full RAG pipeline with CRAG
- **WHEN** the user asks a knowledge question (e.g., "什么是 CRAG？")
- **AND** `route_intent()` returns `free_agent`
- **AND** `analyze_and_route` classifies `route_decision="search"`
- **THEN** the full RAG pipeline SHALL execute: `plan → tool_exec → rerank → grade_evidence → reflect → synthesize`
- **AND** `vector_search` results SHALL be filtered by `grade_evidence_node` before synthesis
- **AND** the user SHALL NOT see raw unfiltered chunks

### Requirement: RAG graph compiled once per shell session
The CLI SHALL compile the RAG LangGraph once during `SkillShell` initialization and reuse the compiled graph for all subsequent free_agent queries in the session.

#### Scenario: Reuse compiled graph across queries
- **WHEN** `SkillShell.__init__` is called
- **THEN** `compile_graph()` SHALL be called exactly once and stored as `self._rag_graph`
- **AND** all free_agent queries in that session SHALL invoke `self._rag_graph.invoke()` without recompiling

### Requirement: RAG status callbacks rendered in CLI
The CLI SHALL display real-time progress from the RAG graph execution using `SkillRenderer`.

#### Scenario: Progress emitted during RAG execution
- **WHEN** `_run_rag_query()` invokes the RAG graph
- **THEN** a `status_callback` function SHALL be injected into `AgentState`
- **AND** each `status_callback(emoji, msg)` call SHALL result in `renderer.print_info(f"{emoji} {msg}")` being printed
- **AND** the user SHALL see progress updates such as "🧠 Analyzing...", "🔍 Executing: vector_search...", "✨ Synthesizing answer..."
