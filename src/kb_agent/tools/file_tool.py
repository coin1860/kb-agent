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

    def read_file(self, file_path: str, start_line: Optional[int] = None, end_line: Optional[int] = None) -> str:
        """
        Reads a file from the allowed directories. Returns content or a descriptive error string.
        """
        try:
            path = Path(file_path)
            
            # If path is relative, make it absolute by checking allowed paths.
            # We don't check if it exists yet, because it might be a missing
            # source file that we need to resolve to an index file later.
            if not path.is_absolute():
                resolved_candidate = None
                for allowed in self.allowed_paths:
                    candidate = allowed / path
                    # Prefer the one that exists
                    if candidate.resolve().exists():
                        resolved_candidate = candidate.resolve()
                        break
                
                # If none exist, just pick the first allowed path as base
                # so the access check passes and the fallback logic can try to find the index file.
                if not resolved_candidate and self.allowed_paths:
                    resolved_candidate = (self.allowed_paths[0] / path).resolve()
                elif resolved_candidate is None:
                    resolved_candidate = path.resolve()
                    
                path = resolved_candidate
            else:
                path = path.resolve()
            
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
                # Fallback: source/X.ext → index/X.md (files are converted during indexing)
                fallback = self._resolve_source_to_index(file_path)
                if fallback and fallback.exists():
                    path = fallback
                else:
                    return f"[ERROR: NOT_FOUND] File '{file_path}' does not exist."

            if not path.is_file():
                return f"[ERROR: NOT_A_FILE] Path '{file_path}' is a directory, not a file."

            content = path.read_text(encoding="utf-8", errors="replace")
            
            if start_line is not None or end_line is not None:
                lines = content.splitlines(True)
                total_lines = len(lines)
                
                start = max(1, start_line) if start_line is not None else 1
                end = min(total_lines, end_line) if end_line is not None else total_lines
                
                if start > end:
                    start, end = end, start
                
                selected_lines = lines[start-1:end]
                header = f"[Lines {start}-{end} of {file_path}]\n"
                return header + "".join(selected_lines)
                
            return content
        except Exception as e:
            return f"[ERROR: READ_FAILED] Unexpected error reading {file_path}: {str(e)}"

    @staticmethod
    def _resolve_source_to_index(file_path: str) -> Optional[Path]:
        """Try to resolve a source file path to its indexed markdown equivalent.
        
        During indexing, source files like `source/file.txt` are converted to
        `index/file.md`. This method attempts that mapping so read_file can
        find the processed version when the original source has been archived.
        """
        p = Path(file_path)
        
        # If we have an index_path configured, just look for the filename.md there.
        # This is the most reliable way since the source path might be relative,
        # absolute, or completely moved.
        settings = config.settings
        if settings and settings.index_path:
            index_dir = settings.index_path.resolve()
            # The archived/indexed file will have the same stem but .md extension
            expected_name = p.stem + ".md"
            candidate = index_dir / expected_name
            if candidate.exists():
                return candidate
                
        # Fallback to simple string replacement for cases without config
        parts = list(p.parts)
        try:
            idx = parts.index("source")
            parts[idx] = "index"
        except ValueError:
            return None
        
        new_path = Path(*parts).with_suffix(".md").resolve()
        return new_path if new_path.exists() else None
