"""
name: run_script
description: Executes a python script located in the sandbox workspace.
parameters: {"script_name": "string", "timeout": "int"}
"""
import subprocess
from pathlib import Path
from typing import Any

def execute(script_name: str, timeout: int = 30, sandbox: Any = None) -> dict:
    try:
        if not sandbox:
            raise ValueError("Sandbox context required for running scripts.")
            
        session_workspace = sandbox.data_folder / "agent_tmp" / sandbox.session_id
        script_path = session_workspace / "scripts" / script_name
        
        sandbox.check_read(script_path)
        
        # Check if venv exists
        venv_python = session_workspace / ".venv" / "bin" / "python"
        cmd = [str(venv_python) if venv_python.exists() else "python3", str(script_path)]
        
        result = subprocess.run(
            cmd,
            cwd=str(session_workspace),
            capture_output=True,
            text=True,
            timeout=timeout
        )
        
        output = result.stdout
        if result.stderr:
            output += f"\nSTDERR:\n{result.stderr}"
            
        if result.returncode == 0:
            return {"status": "success", "result": output}
        else:
            return {"status": "error", "result": f"Script failed with code {result.returncode}:\n{output}"}
            
    except subprocess.TimeoutExpired:
        return {"status": "error", "result": f"Script execution timed out after {timeout} seconds."}
    except Exception as e:
        return {"status": "error", "result": str(e)}
