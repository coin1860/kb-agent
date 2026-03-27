"""
Atomic Python code execution tool for the kb-cli agent.

run_python: execute a Python script file under python_code_path, capture
stdout/stderr, write a .log file, and return the output.
Requires explicit user approval before execution (requires_approval=True).
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

from langchain_core.tools import tool


class SecurityError(Exception):
    """Raised when script_path is outside the allowed python_code directory."""


def _get_python_code_path() -> Path:
    """Return the configured python_code_path."""
    import kb_agent.config as config
    settings = config.settings
    if settings and settings.python_code_path:
        return Path(settings.python_code_path).resolve()
    return (Path.home() / ".kb-agent" / "python_code").resolve()


def _get_data_folder() -> Path:
    """Return the configured data_folder root (fallback: home/.kb-agent)."""
    import kb_agent.config as config
    settings = config.settings
    if settings and settings.data_folder:
        return Path(settings.data_folder).resolve()
    if settings and settings.python_code_path:
        # Derive data_folder as the grandparent of python_code_path (python_code_path = data_folder/python_code)
        return Path(settings.python_code_path).resolve().parent
    return (Path.home() / ".kb-agent").resolve()


def _safe_script_path(script_path: str, base: Path) -> Path:
    """
    Resolve script_path, prioritizing dedicated settings paths (especially python_code/).
    """
    import kb_agent.config as config
    settings = config.settings
    data_folder = _get_data_folder().resolve()
    
    raw = Path(script_path)
    parts = raw.parts
    
    # Check for dedicated prefix and switch base if necessary
    if parts and settings:
        if parts[0] == "python_code" and settings.python_code_path:
            base = Path(settings.python_code_path).resolve()
            script_path = os.path.join(*parts[1:]) if len(parts) > 1 else "."
        elif parts[0] == "output" and settings.output_path:
            base = Path(settings.output_path).resolve()
            script_path = os.path.join(*parts[1:]) if len(parts) > 1 else "."
        elif parts[0] == "temp" and settings.temp_path:
            base = Path(settings.temp_path).resolve()
            script_path = os.path.join(*parts[1:]) if len(parts) > 1 else "."

    if raw.is_absolute():
        resolved = raw.resolve()
    else:
        resolved = (base / script_path).resolve()

    # Security check: Allow any path under base or data_folder
    resolved_str = str(resolved)
    if not (resolved_str.startswith(str(base)) or resolved_str.startswith(str(data_folder))):
        raise SecurityError(
            f"Script path '{script_path}' resolves to '{resolved}' which is "
            f"outside allowed base '{base}' and data folder '{data_folder}'"
        )
    return resolved


@tool
def run_python(
    script_path: str,
    timeout_seconds: int = 60,
) -> str:
    """Execute a Python script file and capture its output.

    The script must be located under data_folder/python_code/.
    stdout and stderr are captured and also written to a .log file
    alongside the script for auditability.

    **This tool REQUIRES user approval before execution.**

    Args:
        script_path: Path to the Python script (relative to data_folder, or
                     absolute path under python_code_path). E.g.,
                     'python_code/<run_id>/step_1.py'.
        timeout_seconds: Maximum execution time in seconds (default 60).

    Returns:
        A JSON-like string with exit_code, stdout, stderr, and log_path.
    """
    base = _get_python_code_path()

    try:
        target = _safe_script_path(script_path, base)
    except SecurityError as e:
        return f"SecurityError: {e}"

    if not target.exists():
        return f"Error: script not found at '{target}'"

    log_path = target.with_suffix(target.suffix + ".log")

    try:
        result = subprocess.run(
            [sys.executable, str(target)],
            capture_output=True,
            text=True,
            timeout=timeout_seconds,
            cwd=str(target.parent),
        )
        stdout = result.stdout
        stderr = result.stderr
        exit_code = result.returncode
        status = "completed"

    except subprocess.TimeoutExpired as e:
        stdout = e.stdout or ""
        stderr = f"TimeoutExpired: script exceeded {timeout_seconds}s"
        exit_code = -1
        status = "timeout"

    except Exception as e:
        stdout = ""
        stderr = f"Execution error: {e}"
        exit_code = -1
        status = "error"

    # Write audit log file
    log_content = (
        f"=== Script: {target} ===\n"
        f"=== Status: {status} | Exit code: {exit_code} ===\n\n"
        f"--- STDOUT ---\n{stdout}\n"
        f"--- STDERR ---\n{stderr}\n"
    )
    try:
        log_path.write_text(log_content, encoding="utf-8")
    except OSError:
        pass  # Non-fatal

    # Truncate for LLM consumption
    stdout_trunc = stdout[:3000] + "\n...(truncated)" if len(stdout) > 3000 else stdout
    stderr_trunc = stderr[:1000] + "\n...(truncated)" if len(stderr) > 1000 else stderr

    return (
        f"exit_code: {exit_code}\n"
        f"status: {status}\n"
        f"python_path: {sys.executable}\n"
        f"stdout:\n{stdout_trunc}\n"
        f"stderr:\n{stderr_trunc}\n"
        f"log_path: {log_path}"
    )


def pip_install(package: str) -> tuple[int, str]:
    """Install a package into the current venv using sys.executable.

    Returns (exit_code, combined_output).
    `sys.executable -m pip install` guarantees the same venv as kb-agent.
    """
    result = subprocess.run(
        [sys.executable, "-m", "pip", "install", package],
        capture_output=True,
        text=True,
        timeout=120,
    )
    return result.returncode, result.stdout + result.stderr


# Mark as requiring approval — stored in module-level registry
# (cannot set attributes on Pydantic StructuredTool directly)
TOOL_APPROVAL_REGISTRY: dict[str, bool] = {
    run_python.name: True,
}


def get_requires_approval(tool) -> bool:
    """Return whether a tool requires user approval before execution."""
    return TOOL_APPROVAL_REGISTRY.get(getattr(tool, 'name', ''), False)
