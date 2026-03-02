## MODIFIED Requirements

### Requirement: Evidence Relevance and Synthesis
The agent must prioritize delivering a thorough, detailed response based on the available retrieved context. The synthesize prompt SHALL instruct the LLM to extract ALL relevant details from evidence and produce comprehensive answers. The synthesizer MUST separate the raw generated answer from the structured source metadata, completely omitting the legacy plain-text `Sources:` footer.

#### Scenario: High-Confidence Evidence Processing
- **WHEN** the grader evaluates retrieved chunks and assigns them scores
- **THEN** it MUST retain a broader set of contexts (removing strict score < 0.3 filtering) to pass maximal signal to the synthesizer.

#### Scenario: Synthesis with Incomplete Evidence
- **WHEN** the synthesizer receives context that only partially answers the query
- **THEN** it MUST attempt to answer the user's query as fully as possible using the retrieved evidence, heavily prioritizing partial answers over outright refusals.
- **AND** it MAY use general background knowledge to glue together or interpret the facts provided in the evidence, while still citing the sources that ground its response using inline bracketed numbers (e.g., `[1]`).

#### Scenario: Thorough answer generation
- **WHEN** the synthesizer receives evidence containing multiple data points, details, or structured data
- **THEN** it MUST extract and include ALL relevant details, data points, and specific information from the evidence
- **AND** it MUST reproduce structured data (tables, lists, technical specs) rather than just paraphrasing them
- **AND** it MUST structure the response using headers, bullet points, and formatting for readability
- **AND** long, well-structured answers SHALL be preferred over terse summaries

#### Scenario: Structured Source Returns
- **WHEN** the synthesizer generates its final payload
- **THEN** it MUST return the textual answer and a structured list of sources (containing `path`, `line`, `score`, and `content`) as distinct fields or a cleanly parseable structure, NEVER appending a plain-text `Sources:` footer to the textual answer.
