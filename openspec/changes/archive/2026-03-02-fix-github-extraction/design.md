# Design: Fix Web Connector Filtering Logic

## Overview
Currently, `WebConnector._fetch_with_requests` attempts to filter out noisy HTML elements (scripts, sidebars, cookie banners) by executing `.decompose()` globally on the entire BeautifulSoup object. This leads to accidental deletion of the entire content body if a parent element matches one of the vague classes (e.g., GitHub's root container has `Layout--sidebarPosition-end`).

### Targeted Fix
Instead of global decomposition, we must:
1. Locate the `main_content` node (e.g., `<article>`, `<main>`, etc.) first.
2. Isolate and clone/extract this localized tree or run the decomposition strictly on the descendants of this node.
3. This prevents a broad CSS selector from accidentally destroying the entire content container just because the container itself has a vague class name attached.

## System Impact

- **WebConnector**: The HTML cleaning logic inside `_fetch_with_requests()` will be updated.
- **Dependencies**: No new modules.
- **Performance**: Similar or improved performance as decomposition runs on a smaller document segment.
