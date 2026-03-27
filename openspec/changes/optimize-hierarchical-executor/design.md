## Context

The current Hierarchical Planner-Executor architecture is robust but "chatty". Each step execution involves multiple sequential LLM calls (Decision -> Resolve -> Execute -> Reflect). For simple milestones (e.g., retrieving a ticket), this results in significant overhead.

## Goals / Non-Goals

**Goals:**
- Reduce average latency for a 2-milestone task by 30-40%.
- Reduce total LLM calls for read-heavy tasks.
- Maintain high accuracy and self-correction capability for complex scripts/writes.

**Non-Goals:**
- Removing the hierarchical architecture.
- Removing reflection for critical write operations or complex Python scripts.

## Decisions

### 1. Selective Reflection (The "Fast-Pass")
- **Rationale**: Read-only tools with clear, non-error outputs do not require LLM validation.
- **Criteria for skipping `_reflect`**:
    - Tool is in `SAFE_READ_TOOLS` (e.g., `jira_fetch`, `vector_search`, `get_knowledge`).
    - `_is_error_result(result)` is `False`.
    - `len(result)` is between 50 and 8000 characters.
- **Rationale for logic**: If it's too short, it might be a hallucinatory "None" or silent failure. If it's too long, it might need summarization or validation.

### 2. Adaptive Context Forwarding (Threshold-based Compression)
- **Rationale**: Compression costs 1 LLM call. With modern models, 8k context is easily manageable.
- **Change**: In `_milestone_execute_loop`, skip `_compress_milestone_result` if `len(raw_result) < 8000` (or approx token equivalent).
- **Target Compression**: If must compress, target is 4,000 tokens to ensure high depth of detail.

### 3. Structural Call Compression (Merging Prompts)
- **Rationale**: Currently, multiple LLM calls are used for micro-decisions (Route -> Preview -> Plan, and Decide -> Resolve). These can be combined to drastically reduce API latency.
- **Change 1 (Unified Planner)**: Combine the routing, intent preview, and milestone planning into a single `generate_plan` call. The model will output its route, summary, and milestones in one JSON response.
- **Change 2 (Resolved Decision)**: In `decide_next_step`, instruct the model to produce both the `thought` and the fully resolved `args` for the tool call. This eliminates the need for a separate `_resolve_args` call during execution.

### 4. "Self-Terminating" Tool Action
- **Rationale**: Save the final `decide_next_step -> final_answer` call.
- **Change**: Update the `PlanStep` or `decide_next_step` system prompt to allow the agent to flag a tool call as the "Milestone Finisher".
- **Implementation**: If a tool call return includes `finish_milestone: true`, the `_execute_milestone` loop exits immediately after that tool's output is recorded.

## Risks / Trade-offs

- **[Risk]** → Structural prompt merging might make prompts too complex for smaller models to follow accurately.
- **[Mitigation]** → Use clear JSON schema examples in the system prompt. Since we are using Gemini Flash/Pro, structured JSON output is highly reliable.
- **[Risk]** → Selective reflection might miss subtle data format errors from a read tool.
- **[Mitigation]** → The *subsequent* milestone's `decide_next_step` will see the raw data and can complain/request a retry if it's unusable.
- **[Trade-off]** → Increasing the forwarding threshold to 8k tokens means slightly higher input token costs for later milestones, but this is offset by saving a high-latency compression call and preserving more detail.
