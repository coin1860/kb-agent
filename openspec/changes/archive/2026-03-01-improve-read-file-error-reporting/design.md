## Context

The `FileTool.read_file` current implementation uses a simple `if not is_allowed: return None` logic. Its wrapper in `agent/tools.py` then converts any `None` into a generic "File not found or access denied" string. This loses specific failure reasons and provides no guidance to the Agent on how to fix a path that is outside allowed boundaries.

## Goals / Non-Goals

**Goals:**
- Differentiate between "File Not Found" and "Access Denied".
- Provide the Agent with the list of `allowed_paths` when an "Access Denied" error occurs.
- Ensure the error message is long/descriptive enough to be clearly distinguished from short valid file contents.

**Non-Goals:**
- Changing the security model (we are keeping the sandbox, just making it more "vocal").
- Automatically expanding `allowed_paths` (that would be a separate proposal if needed).

## Decisions

### 1. Refactor `FileTool.read_file` to raise custom exceptions or return a Result object
Instead of returning `Optional[str]`, we will modify it to return a clear error indicator or let the wrapper handle the logic. 
*Decision*: Modify `read_file` to return a specific error string directly, or change the return type to a more descriptive Union. To keep it simple for the LLM tool call, returning a descriptive string is often best.

### 2. Include `allowed_paths` in the error message
When a path is rejected, the tool will explicitly state: "Access Denied: Path is outside allowed directories. Allowed directories are: [...]". 
*Rationale*: This enables the Agent to realize it needs to use a different base path or check its configuration.

## Risks / Trade-offs

- **Risk**: Returning a long error string might be interpreted as "successful file content" by a very naive LLM.
- **Mitigation**: Prefix the message with a clear `[ERROR: ACCESS_DENIED]` or similar marker that the system prompt or tool definition can warn about.
