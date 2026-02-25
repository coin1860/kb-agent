from pathlib import Path
from typing import Optional
import kb_agent.config as config
import os

class FileTool:
    def __init__(self):
        settings = config.settings
        self.docs_path = settings.docs_path if settings else Path(".")

    def read_file(self, file_path: str) -> Optional[str]:
        """
        Reads a file from the docs directory.
        """
        try:
            # Resolve relative paths against docs_path
            path = Path(file_path)
            if not path.is_absolute():
                path = self.docs_path / path

            # Basic security check: ensure path is within docs_path
            # try:
            #     path.relative_to(self.docs_path)
            # except ValueError:
            #     print(f"Access denied: {path} is outside docs directory.")
            #     return None

            if not path.exists():
                return None

            return path.read_text(encoding="utf-8", errors="replace")
        except Exception as e:
            print(f"Error reading file {file_path}: {e}")
            return None
