## ADDED Requirements

### Requirement: Compress milestone result after sub-loop completion
The system SHALL call `_compress_milestone_result(milestone, raw_result, llm)` after each milestone's sub-loop completes. This function SHALL make a single LLM call (capped at 200 output tokens) to produce a concise paragraph summary of the milestone's raw tool outputs.

#### Scenario: Successful compression of data-fetch milestone
- **WHEN** milestone 1 (data fetch) sub-loop completes with a multi-kilobyte JSON result
- **THEN** `_compress_milestone_result()` is called with the raw result string
- **AND** the returned summary is ≤ 200 tokens
- **AND** the summary preserves structured artefacts: file paths, ticket IDs, numeric values critical to subsequent milestones

#### Scenario: Compression LLM call fails
- **WHEN** the compression LLM call raises an exception or times out
- **THEN** `_compress_milestone_result()` falls back to the first 1000 characters of the raw result, truncated at a newline boundary
- **AND** a warning is logged but execution continues normally

### Requirement: Compressed summaries are forwarded to subsequent milestone prompts
The milestone executor SHALL inject compressed prior-milestone summaries into the `decide_next_step()` user prompt under a `Prior milestone context` section, separate from the current milestone's `tool_history`.

#### Scenario: Third milestone receives two compressed summaries
- **WHEN** milestones 1 and 2 have completed successfully
- **THEN** the `decide_next_step()` prompt for milestone 3 contains two compressed summary paragraphs prefixed by their milestone goal
- **AND** the token count of the prior-context section is bounded by `2 × 200` output tokens from prior compressions

### Requirement: Raw milestone results are persisted in session audit trail
The system SHALL write the uncompressed raw result of each milestone to the session `StepRecord` in addition to the compressed version forwarded to subsequent milestones.

#### Scenario: Audit trail contains full milestone output
- **WHEN** a milestone's sub-loop completes
- **THEN** a `StepRecord` is written with `result_summary` containing the first 500 chars of the raw result (existing behavior for steps)
- **AND** a milestone-level summary entry is added to the session manifest capturing the `milestone.goal` and compressed summary
