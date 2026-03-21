"""
name: ensure_venv
description: Ensures a local python virtual environment exists for the session and installs packages.
parameters: {"packages": "list of strings"}
"""
import subprocess
import venv
from pathlib import Path
from typing import Any, List

def execute(packages: List[str] = None, sandbox: Any = None) -> dict:
    try:
        if not sandbox:
            raise ValueError("Sandbox context required to manage venv.")
            
        session_workspace = sandbox.data_folder / "agent_tmp" / sandbox.session_id
        session_workspace.mkdir(parents=True, exist_ok=True)
        
        venv_path = session_workspace / ".venv"
        
        # Create venv if it doesn't exist
        if not venv_path.exists():
            from venv import EnvBuilder
            # Use EnvBuilder directly for better compatibility
            builder = EnvBuilder(with_pip=True)
            builder.create(venv_path)
            
        if not packages:
            return {"status": "success", "result": "Venv ready (no packages to install)."}
            
        # pip install the requested packages
        pip_path = venv_path / "bin" / "pip"
        cmd = [str(pip_path), "install"] + packages
        
        # Execute
        result = subprocess.run(
            cmd,
            cwd=str(session_workspace),
            capture_output=True,
            text=True,
            timeout=120  # installation might take longer
        )
        
        output = result.stdout
        if result.stderr:
            output += f"\nSTDERR:\n{result.stderr}"
            
        if result.returncode == 0:
            return {"status": "success", "result": f"Packages installed successfully:\n{output}"}
        else:
            return {"status": "error", "result": f"Pip install failed with code {result.returncode}:\n{output}"}
            
    except subprocess.TimeoutExpired:
        return {"status": "error", "result": "Pip install timed out."}
    except Exception as e:
        return {"status": "error", "result": str(e)}
