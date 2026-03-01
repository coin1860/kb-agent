## MODIFIED Requirements

### Requirement: Generate answers with source citations and LLM stats
The system SHALL include source citations in the synthesized answer, referencing the file path and line number of each piece of evidence used, and SHALL append a final formatted block containing aggregated LLM usage statistics (API calls and total tokens) accumulated from the `AgentState`.

#### Scenario: Answer with inline citations and LLM stats
- **WHEN** the `synthesize` node generates an answer from graded evidence
- **THEN** the answer includes numbered footnote references inline (e.g., `[1]`, `[2]`)
- **AND** a citation footer is appended listing each source: `[N] /path/to/file.md:L42`
- **AND** a new line reading `---` followed by a `📊 **LLM Usage Stats:**` block containing token/latency breakdown is appended at the very end of the response

#### Scenario: Evidence without line number metadata
- **WHEN** a context item comes from `vector_search` and lacks a specific line number
- **THEN** the citation references only the file path without line number (e.g., `[N] /path/to/file.md`)

#### Scenario: No evidence available for synthesis
- **WHEN** the `synthesize` node has no context items (all filtered or empty)
- **THEN** the system responds with "I couldn't find relevant information in the knowledge base to answer this question."
- **AND** no citation footer is appended
- **AND** the `📊 **LLM Usage Stats:**` block IS STILL appended to show the cost of processing the unanswerable query
