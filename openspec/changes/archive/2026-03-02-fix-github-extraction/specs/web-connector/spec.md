## MODIFIED Requirements

### Requirement: Automatic web URL resolution
The system SHALL intercept HTTP URLs in user queries, fetch their content, and use it as ad-hoc context to answer the user's question, bypassing the standard RAG or local index database. When fetching raw HTML, the system must robustly filter out non-content elements without inadvertently destroying the main article container itself.

#### Scenario: Aggressive Layouts (e.g., GitHub Repos)
- **WHEN** the `web_connector` (via `markdownify` engine) processes a page with layout parent classes containing "sidebar" or "banner"
- **THEN** the system SHALL extract the localized `main_content` node based on tag heuristics (`<article>`, `<main>`, etc.) first
- **AND** apply CSS-selector-based destructive filtering (e.g. `[class*='sidebar']`) ONLY to the descendants inside this localized subtree
- **AND** preserve the top-level main/article wrapper content itself 
- **AND** successfully convert the rich content to Markdown without truncation
