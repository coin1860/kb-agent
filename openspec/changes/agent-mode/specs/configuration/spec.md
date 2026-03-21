## MODIFIED Requirements

### Requirement: Settings Model
The Settings model SHALL include `llm_providers` (list of LLMProvider), `llm_roles` (LLMRoles), and agent-mode paths (`skills_path`, `output_path`, `agent_tmp_path`, `sessions_path`) in addition to existing fields.

#### Scenario: New config fields loaded
- **WHEN** config JSON contains `llm_providers` and `llm_roles`
- **THEN** system parses them into `LLMProvider` and `LLMRoles` Pydantic models

#### Scenario: Legacy config backward compatible
- **WHEN** config JSON contains only `llm_api_key`, `llm_base_url`, `llm_model`
- **THEN** system initializes with legacy fields and auto-converts to single provider internally

#### Scenario: Agent paths computed from data_folder
- **WHEN** `data_folder` is set and agent-mode paths are not explicitly provided
- **THEN** system computes: `skills_path = data_folder / "skills"`, `output_path = data_folder / "output"`, `agent_tmp_path = data_folder / "agent_tmp"`, `sessions_path = data_folder / "sessions"`

### Requirement: Data Folder Structure
The system SHALL create agent-mode sub-directories (`skills/`, `output/`, `agent_tmp/`, `sessions/`) under the Data Folder on first Agent Mode use.

#### Scenario: Directories created on first use
- **WHEN** Agent Mode is activated for the first time and the sub-directories do not exist
- **THEN** system creates `skills/`, `output/`, `agent_tmp/`, `sessions/` under the configured Data Folder
