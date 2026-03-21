"""
name: read_file
description: Reads a file from the Data Folder sandbox.
parameters: {"file_path": "string"}
"""
from typing import Any

def execute(file_path: str, sandbox: Any = None) -> dict:
    try:
        if not sandbox:
            raise ValueError("Sandbox context required for file reading.")
        allowed_path = sandbox.check_read(file_path)
        with open(allowed_path, 'r', encoding='utf-8') as f:
            content = f.read()
            return {"status": "success", "result": content}
    except Exception as e:
        return {"status": "error", "result": str(e)}
