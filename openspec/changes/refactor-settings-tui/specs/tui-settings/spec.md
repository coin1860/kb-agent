## ADDED Requirements

### Requirement: TUI Two-Level Settings Navigation
The TUI Settings page MUST be split into a two-level structure. The first level presents a list of settings categories (LLM, RAG, Atlassian, General). The second level presents the input fields specifically belonging to the selected category.

#### Scenario: Opening Settings
- **WHEN** the user invokes `/settings`
- **THEN** the Level 1 category selection screen appears.

#### Scenario: Selecting a Category
- **WHEN** the user selects "LLM" from the category list and presses Enter
- **THEN** the UI opens a nested view showing only LLM fields (e.g., API Key, Base URL, Model, Embedding URL, Embedding Model).

#### Scenario: Saving Settings from Detail Screen
- **WHEN** the user modifies fields in a category and selects "Save"
- **THEN** the changes are persisted to `kb-agent.json`, and the user is returned to the Level 1 category selection screen, allowing further navigation or closure via ESC.
