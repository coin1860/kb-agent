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

    def read_file(self, file_path: str) -> Optional[str]:
        """
        Reads a file from the allowed directories.
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
                print(f"Access denied: {path} is outside allowed directories.")
                return None

            if not path.exists():
                return None

            return path.read_text(encoding="utf-8", errors="replace")
        except Exception as e:
            print(f"Error reading file {file_path}: {e}")
            return None
