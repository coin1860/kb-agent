# Proposal: Refactor OpenSpec Specs Organization

## Goal
Improve the discoverability and organization of the `openspec/specs/` directory by implementing a functional grouping strategy using directory prefixes.

## Context
Currently, all specs are flatly listed in `openspec/specs/`, making it difficult to understand the system architecture at a glance.

## Proposed Strategy
Adopt "Option 2": Prefix each spec directory with its functional domain (e.g., `retrieval-`, `ingestion-`). This maintains a flat physical structure while providing logical grouping through alphabetical sorting in IDEs.

## Non-Goals
- Changing the content of the specifications (except for adding `domain` metadata).
- Deeply nesting directories.
