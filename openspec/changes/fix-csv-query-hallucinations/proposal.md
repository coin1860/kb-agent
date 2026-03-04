## Why

The current CSV query tool frequently hallucinates column names because it guesses headers based on user requests, leading to failed pandas queries. By letting the AI first read the valid headers of the CSV and returning those headers securely into the prompt context when a query fails, we can drastically reduce errors and avoid the AI entering a hallucination loop.

## What Changes

- Introduce a new tool or explicit prompt instruction to read the schema (`get_csv_schema_and_sample`) before attempting queries.
- Update `csv_query` prompt in `tools.py` to strongly enforce calling the schema tool before generating a pandas query.
- Enhance the exception handling in `csv_qa_tool.py`'s `csv_query` function to capture real headers and return them along with the error as an Observation, preventing repeated blind guessing.

## Capabilities

### New Capabilities
- `tool-csv-query`: Defines the strict requirement that CSV queries must be preceded by schema interrogation and incorporate resilient error recovery when Pandas operations fail.

### Modified Capabilities


## Impact

- `kb_agent.tools.csv_qa_tool`: New schema tool exported; error handling updated.
- `kb_agent.agent.tools`: Registration of the new CSV info tool and updated prompt for `csv_query`.
- Reduces tokens wasted on repeated failed executions.
