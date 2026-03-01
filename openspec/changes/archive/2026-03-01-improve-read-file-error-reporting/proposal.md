## Why

When `read_file` fails due to security restrictions or missing files, it currently returns a generic string message ("File not found or access denied: ..."). This is problematic because:
1. The message length (e.g., 72 chars) is the only feedback the Agent sees in the execution log, leading to confusion about why a file appears "empty" or "short".
2. The Agent cannot distinguish between a file actually being 72 characters long and a failure to read the file.
3. It lacks actionable context (e.g., which paths *are* allowed).

## What Changes

- **Modified Capability**: `read_file` tool will now return structured error messages or raise clear exceptions that the Agent can interpret.
- **Improved Feedback**: The error message will now include the actual reason (Access Denied vs Not Found) and, in the case of Access Denied, list the allowed base directories to help the Agent self-correct its pathing.

## Capabilities

### New Capabilities
- None

### Modified Capabilities
- `hybrid-retrieval`: The `read_file` tool behavior needs to be more explicit about failures to support better reasoning during retrieval.

## Impact

- `src/kb_agent/tools/file_tool.py`: `FileTool.read_file` will return more descriptive strings or structured data.
- `src/kb_agent/agent/tools.py`: The `@tool` wrapper will be updated to format these errors for the LLM.
