"""
Atomic file operations tool for the kb-cli agent.

write_file: create, overwrite, append, or delete files under data_folder.
Requires explicit user approval before execution (requires_approval=True).
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Optional

from langchain_core.tools import tool


class SecurityError(Exception):
    """Raised when a path traversal or forbidden path is detected."""


def _get_data_folder() -> Path:
    """Return the configured data_folder path."""
    import kb_agent.config as config
    settings = config.settings
    if settings and settings.data_folder:
        return Path(settings.data_folder).resolve()
    # Fallback: use output_path parent
    if settings and settings.output_path:
        return Path(settings.output_path).resolve().parent
    return Path.home() / ".kb-agent"


def _safe_resolve(relative_path: str, base: Path) -> Path:
    """
    Resolve a relative path, prioritizing dedicated settings paths (python_code/, output/, temp/).
    """
    import kb_agent.config as config
    settings = config.settings
    
    raw = Path(relative_path)
    parts = raw.parts
    
    # Check for dedicated prefix and switch base if necessary
    if parts and settings:
        if parts[0] == "python_code" and settings.python_code_path:
            base = Path(settings.python_code_path).resolve()
            relative_path = os.path.join(*parts[1:]) if len(parts) > 1 else "."
        elif parts[0] == "output" and settings.output_path:
            base = Path(settings.output_path).resolve()
            relative_path = os.path.join(*parts[1:]) if len(parts) > 1 else "."
        elif parts[0] == "temp" and settings.temp_path:
            base = Path(settings.temp_path).resolve()
            relative_path = os.path.join(*parts[1:]) if len(parts) > 1 else "."

    resolved = (base / relative_path).resolve()
    try:
        # Security check: must be under the chosen base
        resolved.relative_to(base.resolve())
    except ValueError:
        # Fallback security check: if NOT under chosen base, must at least be under data_folder
        # (Allows writing to a shared data_folder root if prefixes aren't being used strictly)
        data_folder = _get_data_folder().resolve()
        try:
            resolved.relative_to(data_folder)
        except ValueError:
            raise SecurityError(
                f"Path traversal detected: '{relative_path}' resolves outside allowed "
                f"base '{base}' and data_folder '{data_folder}'"
            )
    return resolved


@tool
def write_file(
    path: str,
    content: str = "",
    mode: str = "create",
) -> str:
    """Write, append, or delete a file relative to data_folder.

    Use this tool to persist results, reports, or generated code to disk.
    All paths are relative to data_folder. Absolute paths or path traversal
    attempts (../../) are blocked.

    **Path conventions:**
    - Intermediate/temporary files (used between steps): use ``temp/<filename>``
      (e.g. ``temp/analysis.json``, ``temp/raw_data.csv``).
      These are automatically deleted when the task completes.
    - Final output files explicitly requested by the user (.md, .csv, .pdf, etc.):
      use ``output/<filename>`` (e.g. ``output/report.md``).
      These are kept permanently.

    **This tool REQUIRES user approval before execution.**

    Args:
        path: File path relative to data_folder (e.g. 'temp/analysis.json' or 'output/report.md').
        content: File content to write (ignored for 'delete' mode).
        mode: One of 'create' (fail if exists), 'overwrite' (always write),
              'append' (add to end), 'delete' (remove file).

    Returns:
        A success message with the absolute file path, or an error description.
    """
    data_folder = _get_data_folder()

    try:
        target = _safe_resolve(path, data_folder)
    except SecurityError as e:
        return f"SecurityError: {e}"

    # Validate mode
    valid_modes = {"create", "overwrite", "append", "delete"}
    if mode not in valid_modes:
        return f"Error: invalid mode '{mode}'. Must be one of {sorted(valid_modes)}."

    try:
        if mode == "delete":
            if target.exists():
                target.unlink()
                return f"Deleted: {target}"
            else:
                return f"File not found (nothing to delete): {target}"

        # Ensure parent directories exist
        target.parent.mkdir(parents=True, exist_ok=True)

        if mode == "create" and target.exists():
            return (
                f"Error: file already exists at '{target}'. "
                "Use mode='overwrite' to replace it."
            )

        write_flag = "a" if mode == "append" else "w"
        with open(target, write_flag, encoding="utf-8") as f:
            f.write(content)

        action = {"create": "Created", "overwrite": "Overwrote", "append": "Appended to"}[mode]
        return f"{action}: {target} ({len(content)} chars written)"

    except OSError as e:
        return f"OSError writing '{target}': {e}"


# Mark as requiring approval — stored in module-level registry
# (cannot set attributes on Pydantic StructuredTool directly)
TOOL_APPROVAL_REGISTRY: dict[str, bool] = {
    write_file.name: True,
}


def get_requires_approval(tool) -> bool:
    """Return whether a tool requires user approval before execution."""
    return TOOL_APPROVAL_REGISTRY.get(getattr(tool, 'name', ''), False)
