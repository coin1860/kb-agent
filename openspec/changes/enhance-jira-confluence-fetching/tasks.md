## 1. Jira Connector - Fetch recent comments

- [x] 1.1 Update `JiraConnector._fetch_issue` to call `issue_get_comments(issue_key)` after the issue description is fetched.
- [x] 1.2 Modify `_format_issue` to take `comments` as an argument and format the most recent 10 comments (in reverse chronological order) into a `## Comments` section.

## 2. Jira Connector - Inline Confluence fetching

- [x] 2.1 Refactor Confluence extraction to run a regex over both the `description` and all formatted `comments`.
- [x] 2.2 In `_fetch_issue`, iterate over the collected unique Confluence URL matches, parse the page IDs, and call the `ConfluenceConnector.get_page(page_id)` method to fetch the content directly.
- [x] 2.3 Append the Confluence markdown content directly to the `_format_issue` output (e.g. `## Linked Confluence Page: ...`) and ensure standard Jira caching captures this combined string.

## 3. Section Markers for Reflection Control

- [x] 3.1 In `_format_issue`, add `<!-- NO_ENTITY_EXTRACT -->` before the `## Sub-Tasks` list and the `## Related Issues` list.
- [x] 3.2 Add `<!-- /NO_ENTITY_EXTRACT -->` after both the sub-tasks and related issues lists to close the marked block.

## 4. Reflect Node Updates

- [x] 4.1 In `kb_agent/agent/nodes.py`, update `reflect_node` to pre-process the `context_str` using `re.sub(r'<!-- NO_ENTITY_EXTRACT -->.*?<!-- /NO_ENTITY_EXTRACT -->', '', context_str, flags=re.DOTALL)` before it executes its entity regex lookups.
- [x] 4.2 Verify that `reflect_node` no longer queues sub-tasks and related issues as explicitly requested context, but still queues entities manually discussed in comments/description.
