"""
Atomic shell command execution tool for the kb-cli agent.

run_shell: execute a shell command, capture stdout/stderr, and return
the output.  Designed for CLI tools referenced in skill playbooks
(e.g. qpdf, pdftotext, pdftk, imagemagick, ffmpeg).

Security model:
  - DANGEROUS_PATTERNS blocks obviously destructive patterns (rm -rf, etc.)
  - Working directory is restricted to data_folder subtree by default
  - Always requires explicit user approval before first run; auto-run
    mode is available as a per-session opt-in via the approval UI
"""

from __future__ import annotations

import re
import shlex
import subprocess
from pathlib import Path

from langchain_core.tools import tool

# ─────────────────────────────────────────────────────────────────────────────
# Security guard
# ─────────────────────────────────────────────────────────────────────────────

_DANGEROUS_PATTERNS: list[re.Pattern] = [
    re.compile(r"\brm\s+-[a-zA-Z]*r[a-zA-Z]*f", re.IGNORECASE),   # rm -rf / rm -fr
    re.compile(r"\brm\s+-[a-zA-Z]*f[a-zA-Z]*r", re.IGNORECASE),
    re.compile(r"\bdd\b.*\bof=/dev/", re.IGNORECASE),              # dd to raw device
    re.compile(r":\s*\(\s*\)\s*\{.*\}\s*;", re.DOTALL),            # fork-bomb :(){ ... }
    re.compile(r"\|\s*bash\b", re.IGNORECASE),                     # curl | bash
    re.compile(r"\|\s*sh\b", re.IGNORECASE),
    re.compile(r">\s*/dev/[^n]", re.IGNORECASE),                   # redirect to /dev/* (not /dev/null)
    re.compile(r"\bmkfs\b", re.IGNORECASE),                        # format filesystem
    re.compile(r"\bshred\b", re.IGNORECASE),                       # secure delete
]


class ShellSecurityError(Exception):
    """Raised when a command matches a dangerous pattern."""


def _check_command_safety(command: str) -> None:
    """Raise ShellSecurityError if the command looks dangerous."""
    for pat in _DANGEROUS_PATTERNS:
        if pat.search(command):
            raise ShellSecurityError(
                f"Command blocked by security guard (matched pattern: {pat.pattern!r}). "
                "If this is intentional, run the command manually in your terminal."
            )


# ─────────────────────────────────────────────────────────────────────────────
# Working directory helpers
# ─────────────────────────────────────────────────────────────────────────────

def _get_data_folder() -> Path:
    """Return the configured data_folder root."""
    import kb_agent.config as config
    settings = config.settings
    if settings and settings.data_folder:
        return Path(settings.data_folder).resolve()
    if settings and settings.python_code_path:
        return Path(settings.python_code_path).resolve().parent
    return (Path.home() / ".kb-agent").resolve()


def _resolve_cwd(cwd: str) -> Path:
    """
    Resolve a working directory string to an absolute Path.

    Empty string → data_folder root.
    Relative paths → resolved relative to data_folder.
    Absolute paths → allowed only if under data_folder (security guard).
    """
    data_folder = _get_data_folder()
    if not cwd:
        return data_folder
    p = Path(cwd)
    if p.is_absolute():
        resolved = p.resolve()
        # Allow if under data_folder OR system tmp
        if not (str(resolved).startswith(str(data_folder)) or
                str(resolved).startswith("/tmp") or
                str(resolved).startswith("/var/folders")):
            raise ShellSecurityError(
                f"cwd '{cwd}' resolves to '{resolved}' which is outside "
                f"the allowed data folder '{data_folder}'."
            )
        return resolved
    return (data_folder / cwd).resolve()


# ─────────────────────────────────────────────────────────────────────────────
# Tool definition
# ─────────────────────────────────────────────────────────────────────────────

@tool
def run_shell(
    command: str,
    cwd: str = "",
    timeout_seconds: int = 120,
) -> str:
    """Execute a shell (bash) command and capture its output.

    Use this tool for CLI utilities referenced in skill playbooks such as
    qpdf, pdftotext, pdftk, imagemagick, ffmpeg, pandoc, and similar.
    Do NOT use for arbitrary destructive commands — dangerous patterns
    (rm -rf, curl | bash, etc.) are automatically blocked.

    **This tool REQUIRES user approval before first execution.  After the
    first approval you may select 'Auto-run' to skip confirmations for the
    rest of the current session.**

    Args:
        command: The shell command to execute (passed to bash -c).
        cwd: Working directory (relative to data_folder, or absolute path
             under data_folder).  Defaults to data_folder root.
        timeout_seconds: Maximum execution time in seconds (default 120).

    Returns:
        A structured string with exit_code, stdout, and stderr.
    """
    # Safety check first
    try:
        _check_command_safety(command)
    except ShellSecurityError as e:
        return f"SecurityError: {e}"

    # Resolve working directory
    try:
        work_dir = _resolve_cwd(cwd)
    except ShellSecurityError as e:
        return f"SecurityError: {e}"
    except Exception as e:
        return f"Error resolving cwd '{cwd}': {e}"

    # Ensure cwd exists (tools like qpdf may not create output dirs)
    try:
        work_dir.mkdir(parents=True, exist_ok=True)
    except OSError:
        pass

    # Execute
    try:
        result = subprocess.run(
            command,
            shell=True,
            executable="/bin/bash",
            capture_output=True,
            text=True,
            timeout=timeout_seconds,
            cwd=str(work_dir),
        )
        stdout = result.stdout
        stderr = result.stderr
        exit_code = result.returncode
        status = "completed" if exit_code == 0 else "failed"

    except subprocess.TimeoutExpired as e:
        stdout = (e.stdout or b"").decode(errors="replace") if isinstance(e.stdout, bytes) else (e.stdout or "")
        stderr = f"TimeoutExpired: command exceeded {timeout_seconds}s"
        exit_code = -1
        status = "timeout"

    except Exception as e:
        stdout = ""
        stderr = f"Execution error: {e}"
        exit_code = -1
        status = "error"

    # Truncate for LLM consumption
    stdout_trunc = stdout[:3000] + "\n...(truncated)" if len(stdout) > 3000 else stdout
    stderr_trunc = stderr[:1000] + "\n...(truncated)" if len(stderr) > 1000 else stderr

    return (
        f"exit_code: {exit_code}\n"
        f"status: {status}\n"
        f"cwd: {work_dir}\n"
        f"command: {command}\n"
        f"stdout:\n{stdout_trunc}\n"
        f"stderr:\n{stderr_trunc}"
    )


# Approval registry entry
TOOL_APPROVAL_REGISTRY: dict[str, bool] = {
    run_shell.name: True,
}
