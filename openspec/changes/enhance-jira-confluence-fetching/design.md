## Context

The current `jira.py` connector only fetches the description of a Jira ticket. In practice, crucial decisions and context are often recorded in the ticket comments or in linked Confluence pages. Currently, the agent must make additional tool calls if it infers a missing Confluence page exists, but it entirely misses Jira comments as no such tool exists to fetch them.

Furthermore, `reflect_node.py` uses a naive regex implementation (`\b[a-zA-Z][a-zA-Z0-9]*-\d+\b`) to extract "active entities" (Jira tickets) from any returned context. Because `jira.py` lists sub-tasks and related issues, `reflect_node` queues them all up for retrieval, cluttering the task queue and wasting LLM bandwidth on low-relevance sub-tasks.

## Goals / Non-Goals

**Goals:**
- Fetch the top 10 most recent comments when `jira_fetch` is called.
- Proactively fetch linked Confluence pages mentioned in either the Jira description or the comments.
- Combine the Jira issue details, comments, and nested Confluence text into one cached response string.
- Prevent `reflect_node` from blindly triggering on Sub-tasks and Related Issues identifiers by using markdown comment markers.

**Non-Goals:**
- Recursively fetching Confluence pages (we will strictly stop at a depth of 1: Jira -> Confluence).
- Following any remote links that are not Confluence URLs.
- Fetching full sub-task details in the initial Jira fetch.

## Decisions

1. **Comments Fetching**: 
   - Uses `self.jira.issue_get_comments(key)`. We will only take the last 10 comments (reverse chronological or latest 10) to avoid bloating the context window for highly contested tickets.
2. **Confluence Fetching Inline**:
   - `JiraConnector` will parse Confluence links from the Description and Comment bodies via regex.
   - It will iterate over discovered unique Confluence IDs, call `ConfluenceConnector().get_page(page_id)`, and append the resulting markdown to the Jira issue output.
3. **Section Markers for Extraction Control**:
   - Instead of complex logic to filter regex results in Python, we will wrap the "Sub-Tasks" and "Related Issues" sections of the Jira output with `<!-- NO_ENTITY_EXTRACT -->` and `<!-- /NO_ENTITY_EXTRACT -->` (or similar). 
   - `reflect_node.py` will pre-process the `context_str` to strip out anything between these markers before running the `JIRA_PATTERN` and `CONFLUENCE_PATTERN` regexes. This effectively hides these structural links from the entity extraction engine while still displaying them to the LLM for synthesis.
4. **Caching Strategy**:
   - We will cache the final merged bundle (Ticket + Comments + Confluence) under the Jira ticket key so that subsequent queries about this ticket do not trigger the 2-3 extra API calls. 

## Risks / Trade-offs

- **Risk: Increased API Latency**: Fetching a Jira ticket will now take slightly longer due to comments fetching and sequential/parallel Confluence fetching.
  - *Mitigation*: The aggressive caching of the final assembled string (`APICache().write("jira", issue_key, formatted_issue)`) keeps this cost to only the first fetch.
- **Risk: Context Bloat**: Too many comments or large Confluence pages might overflow the context windows.
  - *Mitigation*: Capping comments to 10 and only going 1 level deep on Confluence links will bound the maximum size.
