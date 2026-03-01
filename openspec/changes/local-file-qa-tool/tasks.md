## 1. Tool Implementation

+ [x] 1.1 Create `LocalFileQATool` class in `src/kb_agent/tools/local_file_qa.py`
+ [x] 1.2 Implement ChromaDB `kb_docs` querying logic filtered by `type`
+ [x] 1.3 Implement distance/score heuristic to classify matches as `(filename match)` vs `(context match)`
+ [x] 1.4 Format output explicitly as an enumerated list (e.g., `1, file name...`)
+ [x] 1.5 Register the tool in `src/kb_agent/agent/tools.py`

## 2. Agent Workflow Updates

+ [x] 2.1 Update `TOOL_DESCRIPTIONS` in `src/kb_agent/agent/nodes.py` to prompt the LLM to use `local_file_qa` when users ask for file summaries or Mexico payment files.
+ [x] 2.2 Update `PLAN_SYSTEM` to instruct the LLM to resolve table index numbers back to the exact filenames using conversation history before calling `read_file`.

## 3. Testing 
- [ ] 3.1 Verify that query "Search for Mexico payment files" returns the 1-indexed formatted table.
- [ ] 3.2 Verify that a follow-up query "Summarize file 1" successfully triggers `read_file` with the correct filename and outputs a summary.
