# Capability: Multi-Turn Memory

## Purpose

Enables the agent's routing and generation phases to leverage conversation history from previous turns, ensuring coherent multi-turn interactions and consistent entity tracking across a session.

## Requirements

### Requirement: Memory context in routing
The agent's memory capability SHALL be expanded to actively inform both retrieval planning and the final generation phase.

#### Scenario: Routing with memory
- **WHEN** the agent processes a multi-turn conversation
- **THEN** it MUST provide previous `AgentState.messages` to the `analyze_and_route` node to direct its operation correctly.

### Requirement: Storing routing context in AgentState
The AgentState dictionary MUST be updated with explicit fields for storing routing metadata across turns.

#### Scenario: Storing variables
- **WHEN** the `analyze_and_route` node produces a decision
- **THEN** it saves `route_decision`, `resolved_query`, and `active_entities` to the state dictionary to prevent duplicate computation downstream.
