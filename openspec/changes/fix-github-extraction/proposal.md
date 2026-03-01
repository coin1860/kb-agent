# Fix Web Connector Truncation on GitHub Pages

## Current State

The `web_connector` (specifically `markdownify` engine) truncates the majority of content when fetching modern React-based sites like GitHub. Due to aggressive, wildcard DOM selection (`[class*='sidebar']`), it accidentally targets and decomposes the outer container of the core document content (`<article>`), resulting in heavily truncated output.

## Desired State

The connector should correctly isolate and extract the core document (`<article>` or `<main>`) **before** running destructive filtering logic, preserving the user's intended target content while still stripping extraneous UI (popups, sidebars, banners) from within that localized scope.

## Rationale

Fixing this logic allows the RAG engine to properly process GitHub repositories, readmes, and other modern sites that use semantic tagging without inadvertently destroying the content base. It ensures robust fetching for the agent to augment its knowledge base.
