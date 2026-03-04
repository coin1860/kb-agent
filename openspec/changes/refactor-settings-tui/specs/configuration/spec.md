## ADDED Requirements

### Requirement: Nested Configuration Structure
The system SHALL organize configuration parameters into nested logical groups: `llm`, `rag`, `atlassian`, and `general`. The underlying `kb-agent.json` file MUST persist this structure.

#### Scenario: Agent Load Settings
- **WHEN** the agent starts and loads configuration
- **THEN** it correctly maps config properties to `config.settings.llm`, `config.settings.rag`, `config.settings.atlassian`, and `config.settings.general` namespaces.

#### Scenario: JSON Persistence
- **WHEN** settings are saved to disk
- **THEN** `kb-agent.json` produces a nested JSON object reflecting the distinct sub-schemas instead of a flat array of keys.
