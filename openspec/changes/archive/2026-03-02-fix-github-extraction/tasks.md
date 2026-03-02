## 1. Context Extraction Robustness Fix

- [x] 1.1 In `src/kb_agent/connectors/web_connector.py`, modify `_fetch_with_requests` to identify `main_content` *before* executing `.decompose()` filtering on CSS selector patterns.
- [x] 1.2 Apply `extract()` or isolated `select(selector)` loop scoped to just the cloned/isolated tree or by avoiding deleting the `main_content` element if a match overlaps with the container tag itself.

## 2. Verification
- [x] 2.1 Test fetching a GitHub README URL to verify that truncation no longer occurs.
