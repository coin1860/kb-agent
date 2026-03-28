# Skill Agent Loop

## Purpose
The Skill Agent Loop is the core execution engine for KB-CLI skills, responsible for taking a high-level goal or milestone and iteratively deciding and executing steps to achieve it.

## Requirements

### Requirement: Native Tool Calling loop
The agent execution loop MUST use LangChain's native `bind_tools()` to invoke tools instead of instructing the LLM to output a JSON string describing the tool name and arguments.

#### Scenario: Tool bound to LLM
- **WHEN** the agent decides its next step
- **THEN** it MUST use the `llm_with_tools` interface, where `response.tool_calls` contains the structured tool request

### Requirement: Message History Truncation
The agent MUST manage its execution memory using a standard LangChain message history rather than a custom JSON list.

#### Scenario: Memory accumulation
- **WHEN** an iteration of the tool loop completes
- **THEN** an `AIMessage` with `tool_calls` MUST be appended, followed by a `ToolMessage` containing the tool's result string

### Requirement: Passive Reflection
The agent MUST NOT invoke `_reflect` for non-error tool outputs.

#### Scenario: Successful tool execution
- **WHEN** a tool executes and its output does not indicate an error (via `_is_error_result`)
- **THEN** the agent MUST NOT call the reflection LLM and should proceed immediately to the next iteration

### Requirement: Output Summarization Optimization
The agent MUST NOT call the Python summarization LLM if the output string is below a length threshold (e.g., 2000 characters).

#### Scenario: Short stdout from python
- **WHEN** `run_python` returns a short output (< 2000 chars)
- **THEN** the system MUST display the raw string directly instead of summarizing it
