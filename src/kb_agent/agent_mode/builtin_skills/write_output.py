"""
name: write_output
description: Writes an output file to the allowed sandbox folder (e.g., output/).
parameters: {"file_path": "string", "content": "string"}
"""
from typing import Any

def execute(file_path: str, content: str, sandbox: Any = None) -> dict:
    try:
        if not sandbox:
            raise ValueError("Sandbox context required for file writing.")
        allowed_path = sandbox.check_write(file_path)
        
        # Ensure parent directories exist
        allowed_path.parent.mkdir(parents=True, exist_ok=True)
        
        with open(allowed_path, 'w', encoding='utf-8') as f:
            f.write(content)
        return {"status": "success", "result": f"File written to {file_path}"}
    except Exception as e:
        return {"status": "error", "result": str(e)}
