---
title: RAG Synthesis Pipeline
domain: synthesis
---

# rag-synthesis Specification

## Purpose
TBD - Defines rules for synthesizing answers and evaluating evidence.

## Requirements

### Requirement: Evidence Relevance and Synthesis
The agent must prioritize delivering a "best-effort" response based on the available retrieved context over strictly refusing to answer when context is partial or incomplete.

#### Scenario: High-Confidence Evidence Processing
- **WHEN** the grader evaluates retrieved chunks and assigns them scores
- **THEN** it MUST retain a broader set of contexts (removing strict score < 0.3 filtering) to pass maximal signal to the synthesizer.

#### Scenario: Synthesis with Incomplete Evidence
- **WHEN** the synthesizer receives context that only partially answers the query
- **THEN** it MUST attempt to answer the user's query as fully as possible using the retrieved evidence, heavily prioritizing partial answers over outright refusals.
- **AND** it MAY use general background knowledge to glue together or interpret the facts provided in the evidence, while still citing the sources that ground its response.
