## Why

The current KB-CLI agent implementation, while migrated to native `bind_tools()`, still operates in a blocking manner. The user has to wait for the entire LLM response to be generated before seeing any output. For complex reasoning steps (the "Think" part of ReAct), this leads to a "frozen" interface which degrades the user experience. 

Streaming the LLM's thought process as it happens will make the agent feel more responsive and "alive", aligning with OpenClaw 2026 design principles.

## What Changes

We will implement streaming support in the `decide_next_step` loop. Instead of waiting for the full `AIMessage`, we will yield chunks as they arrive. The CLI renderer will be updated to display these chunks in real-time within the "Think" or "Act" blocks. This requires using LangChain's `.astream()` or `.stream()` methods and adapting the `SkillShell` loops to handle asynchronous or generator-based responses.

## Capabilities

### New Capabilities
- `agent-streaming-responses`: Real-time streaming of agent reasoning and tool extraction to the CLI.

### Modified Capabilities
- `skill-agent-loop`: Update the core decision loop requirement to support streaming interaction.

## Impact

- `src/kb_agent/skill/planner.py`: `decide_next_step` will be updated to support streaming (likely via a generator or async generator).
- `src/kb_agent/skill/shell.py`: The execution sub-loops will be refactored to iterate over the stream.
- `src/kb_agent/skill/renderer.py`: New methods or updates to existing methods to support partial, incremental UI updates in the terminal using `Rich`.
