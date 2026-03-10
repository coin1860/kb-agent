# Capability: Stateful Routing

## Purpose

Provides a dedicated analyze-and-route gateway node that evaluates conversation context, resolves ambiguous references, and extracts active entities before dispatching queries to the appropriate pipeline stage (direct synthesis vs. tool-based retrieval).

## Requirements

### Requirement: Analyze and Route Node
The agent MUST process incoming requests through a dedicated `analyze_and_route` node before planning tool execution. This node MUST evaluate the complete conversation history to determine the appropriate routing path.

#### Scenario: Chitchat and Follow-ups
- **WHEN** the user asks a question that can be answered entirely using the conversation history (e.g. "Translate the above to English")
- **THEN** the router MUST output a direct routing decision and skip the tool retrieval phase entirely.

#### Scenario: Information Retrieval Needed
- **WHEN** the user asks a question that requires external knowledge or tool usage
- **THEN** the router MUST output a search routing decision, rewrite the query to resolve historical references, and extract active entities.

### Requirement: Active Entity Extraction
The routing node MUST identify and extract key entities (e.g., Jira ticket IDs like PROJ-123, specific confluence pages, URLs, file paths) mentioned in previous turns strings and pass them into the `AgentState`.

#### Scenario: Propagating entities to planner
- **WHEN** active entities are extracted and a search route is decided
- **THEN** explicitly pass the entities down to the `plan_node` via `AgentState.active_entities`.

### Requirement: Resolved Query Rewriting
The routing node MUST rewrite queries containing pronouns (e.g. "it", "that issue") into grammatically complete, unambiguous queries using context from the history.

#### Scenario: Resolving ambiguous references
- **WHEN** the user asks "What is the status of that ticket?" after a previous message about "FSR-123"
- **THEN** the router MUST rewrite the query to "What is the status of FSR-123?" before sending it to the retrieval tools.
