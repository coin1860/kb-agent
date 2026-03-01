from pathlib import Path
from typing import Optional
import kb_agent.config as config
import os

class FileTool:
    def __init__(self):
        settings = config.settings
        # We allow reading from source docs path (raw) and index path (processed/summaries)
        self.allowed_paths = []
        if settings:
            if settings.source_docs_path:
                self.allowed_paths.append(settings.source_docs_path.resolve())
            if settings.index_path:
                self.allowed_paths.append(settings.index_path.resolve())

    def read_file(self, file_path: str) -> str:
        """
        Reads a file from the allowed directories. Returns content or a descriptive error string.
        """
        try:
            path = Path(file_path).resolve()

            # Security Check: Ensure path is within allowed directories
            is_allowed = False
            for allowed in self.allowed_paths:
                if path.is_relative_to(allowed):
                    is_allowed = True
                    break

            if not is_allowed:
                allowed_str = ", ".join([str(p) for p in self.allowed_paths])
                return f"[ERROR: ACCESS_DENIED] Path '{file_path}' is outside allowed directories. Allowed directories are: [{allowed_str}]"

            if not path.exists():
                return f"[ERROR: NOT_FOUND] File '{file_path}' does not exist."

            if not path.is_file():
                return f"[ERROR: NOT_A_FILE] Path '{file_path}' is a directory, not a file."

            return path.read_text(encoding="utf-8", errors="replace")
        except Exception as e:
            return f"[ERROR: READ_FAILED] Unexpected error reading {file_path}: {str(e)}"
