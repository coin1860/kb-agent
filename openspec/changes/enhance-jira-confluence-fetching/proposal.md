## Why

When answering questions about Jira tickets, the LLM often needs the context hidden within the ticket's comments or Confluence pages linked from the ticket. The current setup only fetches Jira issue descriptions and forces a roundtrip for the agent to figure out if it needs to fetch Confluence, while completely missing Jira comments. Furthermore, the `reflect_node` extracts all Jira keys from the context (e.g. from the Sub-tasks list), causing an explosion of sub-task fetching when they aren't explicitly needed. Proactively fetching and formatting this data effectively will improve answer quality and reduce redundant planner steps.

## What Changes

- Fetch Jira issue comments (up to the 10 most recent) when fetching a Jira issue.
- Proactively fetch the content of Confluence pages linked from the Jira description or comments.
- Only traverse to Confluence pages 1 level deep (do not recursively fetch from Confluence or fetch other types of remote links).
- Format the final compiled Jira content (description + comments + inline Confluence content) into a single result and cache it as a unit.
- Implement section markers (e.g., `<!-- NO_ENTITY_EXTRACT -->`) around the Sub-tasks and Related Issues lists.
- Update `reflect_node` to ignore text inside these section markers when regex-matching so it only extracts explicitly discussed entities.

## Capabilities

### New Capabilities
- `jira-confluence-integration`: Proactive, 1-level deep inline fetching of Confluence pages associated with Jira tickets, plus comment extraction.

### Modified Capabilities
- `reflection-replanning`: Updating the entity extraction logic in `reflect_node` to respect section markers, preventing the blind extraction of sub-tasks and related issues.

## Impact

- `kb_agent.connectors.jira`: Will be updated to make extra API requests for comments and remote links, and will import/invoke the Confluence connector.
- `kb_agent.agent.nodes`: `reflect_node` regex extraction logic will be updated to respect ignore markers.
- RAG Agent Performance: Will reduce unnecessary tool calls for sub-tasks and drastically improve context available for Jira issues.
