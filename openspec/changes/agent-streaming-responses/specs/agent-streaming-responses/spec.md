## ADDED Requirements

### Requirement: Streaming Decision Generator
The `decide_next_step` function MUST return a generator (or an object with a `.stream()` method) that yields incremental updates about the agent's thought process and tool selection.

#### Scenario: Real-time thought streaming
- **WHEN** the LLM generates a partial thought (text content)
- **THEN** it MUST be yielded immediately as a chunk for the UI to display

### Requirement: Progressive UI Updates
The `SkillRenderer` and `SkillShell` MUST support progressive updates to the terminal UI, allowing partial text to be appended or refreshed in the current "Think" block without full-screen repaints or flickering.

#### Scenario: Appending thought chunks
- **WHEN** a thought chunk is received from the decision stream
- **THEN** the CLI renderer MUST update the active thought display to include the new text

## MODIFIED Requirements

### Requirement: Native Tool Calling loop (from skill-agent-loop)
#### Scenario: Streaming tool extraction
- **WHEN** a tool call is being generated in the stream
- **THEN** the system MUST wait for the tool call arguments to be fully populated before attempting to extract and execute the tool
