## ADDED Requirements

### Requirement: LLM Provider Registry
The system SHALL support multiple LLM provider configurations, each with a name, base URL, API key, and list of available models.

#### Scenario: Multiple providers configured
- **WHEN** config contains `llm_providers` array with multiple provider entries
- **THEN** system creates a `ChatOpenAI` client for each provider/model combination and stores them in a lookup registry

#### Scenario: Single provider configured
- **WHEN** config contains only one provider
- **THEN** system creates clients for all models under that provider

### Requirement: Role-Based LLM Routing
The system SHALL route LLM calls to specific provider/model pairs based on the calling context's role (strong, base, fast).

#### Scenario: Strong role used for complex reasoning
- **WHEN** a node requires the "strong" LLM role (e.g., Agent plan, reflect, synthesize)
- **THEN** `LLMRouter.get("strong")` returns the client mapped to the configured strong model

#### Scenario: Base role used for routine tasks
- **WHEN** a node requires the "base" LLM role (e.g., RAG plan, grade evidence)
- **THEN** `LLMRouter.get("base")` returns the client mapped to the configured base model

#### Scenario: Fast role fallback
- **WHEN** a node requests the "fast" role but no fast model is configured
- **THEN** `LLMRouter.get("fast")` falls back to the base model

### Requirement: Backward Compatible Config Migration
The system SHALL automatically migrate legacy single-LLM config to the new multi-provider format.

#### Scenario: Old config format loaded
- **WHEN** config contains `llm_api_key`, `llm_base_url`, `llm_model` but no `llm_providers`
- **THEN** system auto-converts to a single provider named "default" with all roles pointing to the same model

#### Scenario: New config format takes precedence
- **WHEN** config contains both old-style LLM fields and new `llm_providers`/`llm_roles`
- **THEN** system uses `llm_providers`/`llm_roles` and ignores old-style fields

### Requirement: LLMRouter Class
The system SHALL provide an `LLMRouter` class with `get(role: str)` method and convenience properties `strong`, `base`, `fast`.

#### Scenario: Router initialized from config
- **WHEN** application starts and config is loaded
- **THEN** `LLMRouter` is initialized with all provider clients and role mappings, replacing the current `_build_llm()` function
