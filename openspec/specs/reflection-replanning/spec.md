# Capability: Reflection and Re-planning

## Purpose
Implements a precision-oriented feedback loop that extracts explicit entity IDs (Jira, Confluence) from search results using rule-based reflection, and prioritizes those entities for targeted retrieval without additional LLM planning calls.

## Requirements

### Requirement: Active Entity Extraction from Context
The system SHALL execute the `reflect_node` directly after `grade_evidence_node`. Using strict zero-LLM Regex patterns, the system SHALL scan all retrieved context within the iteration loop to extract exact matching strings for structured queries to Jira and Confluence.

#### Scenario: Extract Jira Issue ID
- **WHEN** the `reflect_node` scans a retrieved chunk containing `FSR-123`
- **THEN** it matches the exact JIRA Regex `r'\b[A-Z]+-\d+\b'`
- **AND** it constructs a new pending task in `AgentState.task_queue` if the `id` does not exist in `attempted_task_ids`.
- **AND** it stores the task logic `{name: "jira_fetch", args: {"issue_key": "FSR-123"}}`

#### Scenario: Extract Confluence Page ID
- **WHEN** the `reflect_node` scans a retrieved chunk containing `123456789`
- **THEN** it checks context surrounding the 9+ digit substring for valid keywords (e.g., "confluence", "page", "wiki").
- **AND** upon validation, matches the exact Confluence Regex `r'\b\d{9,}\b'`
- **AND** it appends a new parsed task to `AgentState.task_queue`.

### Requirement: Track Attempted Tasks
The system SHALL track explicit items accessed and prevent circular execution loops of identical tasks.

#### Scenario: Ignore Previously Parsed JIRA Tickets
- **WHEN** a new iteration loop returns search context containing `FSR-123`
- **THEN** the system checks `attempted_task_ids` 
- **AND** since `FSR-123` is already in the list, the system skips adding it to the queue.

### Requirement: Task Queue Precision Re-planning
The `plan_node` SHALL prioritize explicitly defined tasks found in `task_queue` during iteration retries over LLM vector fallback routes. 

#### Scenario: Bypass LLM during Precision Execution
- **WHEN** the graph enters `plan_node` and `iteration > 0`
- **THEN** it pulls exact tasks from `task_queue` assigning them to `pending_tool_calls`
- **AND** the LLM generation phase is fully skipped, logging 0 tokens consumed.

### Requirement: Handle Dead-End Extraction Errors
The `reflect_node` SHALL declare its verdict and redirect control appropriately, managing knowledge gaps accurately.

#### Scenario: Exhaustion with Known Gaps
- **WHEN** `task_queue` is empty and relevance `grader_action` is not GENERATE
- **THEN** `reflect_node` sets `reflection_verdict` to `exhausted`
- **AND** if an ID failed retrieval repeatedly, logs text describing the inability to find the related info explicitly in `knowledge_gaps`.
- **AND** the graph unconditionally branches to `synthesize_node`.
