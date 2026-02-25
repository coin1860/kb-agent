import shutil
import subprocess
import json
import os
import re
from pathlib import Path
from typing import List, Dict, Any
import kb_agent.config as config
import logging

logger = logging.getLogger("kb_agent")

class GrepTool:
    def __init__(self):
        settings = config.settings
        self.docs_path = settings.index_path if settings else Path(".")

    def search(self, query: str) -> List[Dict[str, Any]]:
        """
        Searches for the query string in the docs directory.
        Tries to use `rg` (ripgrep) if available, otherwise falls back to Python-based search.
        """
        if shutil.which("rg"):
             try:
                 return self._ripgrep_search(query)
             except Exception as e:
                 logger.warning(f"Ripgrep failed: {e}. Falling back to Python.")
                 return self._python_search(query)
        else:
             logger.warning("Ripgrep (rg) not found in PATH. Using Python search.")
             return self._python_search(query)

    def _ripgrep_search(self, query: str) -> List[Dict[str, Any]]:
        # Run rg command
        cmd = ["rg", "--json", "-i", query, str(self.docs_path)]
        process = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            encoding="utf-8"
        )

        if process.returncode not in [0, 1]:
             raise Exception(f"Ripgrep error code {process.returncode}")

        results = []
        for line in process.stdout.splitlines():
            try:
                data = json.loads(line)
                if data.get("type") == "match":
                    # Extract path
                    path_data = data["data"]["path"]
                    path = path_data["text"] if isinstance(path_data, dict) else str(path_data)

                    line_num = data["data"]["line_number"]

                    # Extract content
                    lines_data = data["data"]["lines"]
                    content = lines_data["text"] if isinstance(lines_data, dict) else str(lines_data)

                    results.append({
                        "file_path": path,
                        "line": line_num,
                        "content": content.strip()
                    })
            except (json.JSONDecodeError, KeyError, TypeError):
                continue
        return results

    def _python_search(self, query: str) -> List[Dict[str, Any]]:
        results = []
        try:
            pattern = re.compile(query, re.IGNORECASE)
        except re.error:
            return []

        for root, _, files in os.walk(self.docs_path):
            for file in files:
                if file.lower().endswith(".md"):
                    path = os.path.join(root, file)
                    try:
                        with open(path, "r", encoding="utf-8", errors="ignore") as f:
                            for i, line in enumerate(f, 1):
                                if pattern.search(line):
                                    results.append({
                                        "file_path": path,
                                        "line": i,
                                        "content": line.strip()
                                    })
                    except Exception:
                        continue
        return results
