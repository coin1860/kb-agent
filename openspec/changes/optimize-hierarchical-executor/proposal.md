- **Selective Reflection**: Implement a "Fast-Pass" heuristic to skip LLM-based `_reflect` calls for non-critical tools when output is successful.
- **Adaptive Context Compression**: 8k token threshold for forwarding; 4k tokens target for compression.
- **Structural Call Compression**: 
    - **Merge Setup**: Combine `Route`, `Preview`, and `Plan` into a single "Unified Analysis & Planning" call.
    - **Merge Micro-decisions**: Combine `Decide` and `Resolve` into a single "Resolved Decision" call inside milestones, outputting `thought` and `tool_call` (with concrete arguments) simultaneously.
- **Implicit Milestone Termination**: Optimize the milestone loop to reduce the "confirmation call" overhead.

## Capabilities

### New Capabilities
- `execution-optimization`: Optimizing the hierarchical execution loop for speed and token efficiency via structural prompt merging.

### Modified Capabilities
- `skill-execution`: Updating execution logic to support unified calls and conditional reflection.

## Impact

- `src/kb_agent/skill/planner.py`: Major prompt refactoring for Unified Planning.
- `src/kb_agent/skill/shell.py`: Logic for consolidated routing and adaptive context.
- `src/kb_agent/skill/executor.py`: Skills-based parameter resolution moved into the decision phase.
