## 1. Tool Implementation

- [x] 1.1 Update `FileTool.read_file` in `src/kb_agent/tools/file_tool.py` to return descriptive error strings.
- [x] 1.2 Update `read_file` tool wrapper in `src/kb_agent/agent/tools.py` to pass through or format these error strings.

## 2. Verification

- [x] 2.1 Create a test script to verify `read_file` behavior for:
    - Success (valid path)
    - Not Found (missing file in allowed path)
    - Access Denied (path outside allowed paths)
- [x] 2.2 Verify that "Access Denied" error includes the list of allowed directories.
