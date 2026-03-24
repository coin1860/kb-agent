## ADDED Requirements

### Requirement: SKILL_TOOLS list in agent/tools.py
The system SHALL define a `SKILL_TOOLS` list in `agent/tools.py` that equals `ALL_TOOLS + [write_file, run_python]`. The existing `ALL_TOOLS` list SHALL remain unchanged. The `SKILL_TOOLS` list SHALL be used exclusively by the skill executor; the RAG graph continues to use `ALL_TOOLS`.

#### Scenario: SKILL_TOOLS is a superset of ALL_TOOLS
- **WHEN** `SKILL_TOOLS` is inspected
- **THEN** it contains all tools in `ALL_TOOLS` plus `write_file` and `run_python`

#### Scenario: RAG graph unaffected
- **WHEN** the existing RAG graph is compiled
- **THEN** it uses `ALL_TOOLS` and has no reference to `write_file` or `run_python`

---

### Requirement: requires_approval metadata on skill tools
Each `@tool`-decorated function used in skill execution SHALL expose a `requires_approval: bool` attribute accessible at runtime. For tools in `ALL_TOOLS` this SHALL be `False`. For `write_file` and `run_python` this SHALL be `True`.

#### Scenario: Read-only tool approval flag
- **WHEN** `vector_search.requires_approval` is accessed
- **THEN** it returns `False`

#### Scenario: Write tool approval flag
- **WHEN** `write_file.requires_approval` is accessed
- **THEN** it returns `True`
