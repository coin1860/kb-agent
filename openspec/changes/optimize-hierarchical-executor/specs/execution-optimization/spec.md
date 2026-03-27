## ADDED Requirements

### Requirement: Selective Reflection for Safe Tools
The system SHALL skip the LLM reflection step (`_reflect`) for tools categorized as `SAFE_READ_TOOLS` if the output is successful, non-empty, and within safe character limits.

#### Scenario: Skipping reflection for successful Jira fetch
- **WHEN** the tool `jira_fetch` returns a valid JSON string with 500 characters
- **THEN** the system SHALL proceed to the next decision without calling the reflection LLM

#### Scenario: Enforcing reflection for empty or short output
- **WHEN** a `SAFE_READ_TOOLS` returns an empty string or less than 50 characters
- **THEN** the system SHALL call the reflection LLM to verify the result

#### Scenario: Enforcing reflection for critical tools
- **WHEN** the tool `run_python` or `write_file` is executed
- **THEN** the system SHALL ALWAYS call the reflection LLM regardless of output status

### Requirement: Adaptive Context Compression Threshold
The system SHALL bypass the intermediate LLM compression step (`_compress_milestone_result`) if the raw output of a finished milestone is below a specific character threshold (e.g., 8,000 characters).

#### Scenario: Bypassing compression for small output
- **WHEN** a milestone completes with a raw result of 3,000 characters
- **THEN** the system SHALL forward the raw result directly as `prior_context` to the next milestone loop

#### Scenario: Compressing large milestone output
- **WHEN** a milestone completes with a raw result of 15,000 characters
- **THEN** the system SHALL call the compression LLM to summarize the result to approximately 4,000 tokens

### Requirement: Structural Call Compression
The system SHALL combine related prompt steps into unified LLM calls to reduce network overhead. Specifically, Route, Preview, and Plan should be combined into a single Unified Planning step, and Decide and Resolve should be combined into a single Resolved Decision step.

#### Scenario: Unified Planning
- **WHEN** a user provides a new command
- **THEN** the agent SHALL perform routing (intent), generate a summary, and extract milestones in a single JSON response

#### Scenario: Resolved Decision
- **WHEN** the agent decides the next step during a milestone
- **THEN** the agent SHALL output its tools and fully resolved arguments directly, skipping secondary `_resolve_args` calls

### Requirement: Implicit Milestone Termination Signal
The system SHALL allow the decision loop to signal that a specific tool execution marks the completion of the current milestone goal, bypassing the need for a final "stop" verification call.

#### Scenario: Early termination after reaching goal
- **WHEN** the agent returns a tool action with a `finish_milestone: true` flag in its metadata/reason
- **THEN** the milestone execution loop SHALL terminate immediately after the tool execution succeeds
