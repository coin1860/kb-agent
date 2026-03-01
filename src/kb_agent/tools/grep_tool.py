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
                 results = self._ripgrep_search(query)
             except Exception as e:
                 logger.warning(f"Ripgrep failed: {e}. Falling back to Python.")
                 results = self._python_search(query)
        else:
             logger.warning("Ripgrep (rg) not found in PATH. Using Python search.")
             results = self._python_search(query)
             
        return results

    def _ripgrep_search(self, query: str) -> List[Dict[str, Any]]:
        # Run rg command with -C 10 (context lines)
        cmd = ["rg", "--json", "-i", "-C", "10", query, str(self.docs_path)]
        process = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            encoding="utf-8"
        )

        if process.returncode not in [0, 1]:
             raise Exception(f"Ripgrep error code {process.returncode}")

        # Ripgrep with --json and -C groups results in a specific way.
        # It outputs "begin", "match", "context", "end" event types.
        # We will manually merge them into contiguous passages.
        passages: Dict[str, List[Dict[str, Any]]] = {}
        
        for line in process.stdout.splitlines():
            try:
                data = json.loads(line)
                evt_type = data.get("type")
                
                if evt_type in ["match", "context"]:
                    path_data = data["data"]["path"]
                    path = path_data["text"] if isinstance(path_data, dict) else str(path_data)
                    line_num = data["data"]["line_number"]
                    lines_data = data["data"]["lines"]
                    content = lines_data["text"] if isinstance(lines_data, dict) else str(lines_data)
                    
                    if path not in passages:
                        passages[path] = []
                    
                    passages[path].append({
                        "line": line_num,
                        "content": content,
                        "is_match": evt_type == "match"
                    })
            except (json.JSONDecodeError, KeyError, TypeError):
                continue
                
        # Merge lines into passages (within 20 lines of each other)
        results = []
        for path, lines in passages.items():
            lines.sort(key=lambda x: x["line"])
            
            if not lines:
                continue
                
            current_passage = [lines[0]]
            
            for i in range(1, len(lines)):
                if lines[i]["line"] - current_passage[-1]["line"] <= 20:
                    current_passage.append(lines[i])
                else:
                    results.append(self._format_passage(path, current_passage))
                    current_passage = [lines[i]]
                    
            if current_passage:
                results.append(self._format_passage(path, current_passage))
                
        return results

    def _format_passage(self, path: str, lines: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Format a list of lines into a single passage result."""
        content_lines = []
        match_lines = []
        for line in lines:
            line_text = line["content"].strip("\n") # keep leading space, strip traling newline
            if line["is_match"]:
                match_lines.append(line["line"])
            content_lines.append(line_text)
            
        return {
            "file_path": path,
            "line": match_lines[0] if match_lines else lines[0]["line"],
            "content": "\n".join(content_lines)
        }

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
                            all_lines = f.readlines()
                            
                        matches = []
                        for i, line in enumerate(all_lines, 1):
                            if pattern.search(line):
                                matches.append(i)
                                
                        if not matches:
                            continue
                            
                        # Build context windows for python fallback
                        passages = []
                        for match_line in matches:
                            start_line = max(1, match_line - 10)
                            end_line = min(len(all_lines), match_line + 10)
                            
                            # check if we can merge with previous passage
                            if passages and start_line - passages[-1]["end_line"] <= 20: # merging overlapping or close ones
                                passages[-1]["end_line"] = end_line
                                passages[-1]["match_lines"].append(match_line)
                            else:
                                passages.append({
                                    "start_line": start_line,
                                    "end_line": end_line,
                                    "match_lines": [match_line]
                                })
                                
                        for p in passages:
                            content = "".join(all_lines[p["start_line"]-1 : p["end_line"]])
                            results.append({
                                "file_path": path,
                                "line": p["match_lines"][0],
                                "content": content.strip("\n")
                            })
                    except Exception:
                        continue
        return results
