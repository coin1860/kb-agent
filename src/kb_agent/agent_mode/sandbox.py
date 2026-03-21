import os
from pathlib import Path
from kb_agent.config import settings

class SandboxViolationError(Exception):
    """Raised when a sandbox path policy is violated."""
    pass

class SandboxContext:
    def __init__(self, session_id: str):
        self.session_id = session_id
        if not settings or not settings.data_folder:
            raise ValueError("Data folder is not configured. Sandbox requires a data folder.")
        
        # We must resolve all paths to ensure robust comparison
        self.data_folder = Path(settings.data_folder).resolve()
        
        # Define permission table
        self._read_only_paths = [
            (self.data_folder / "index").resolve(),
            (self.data_folder / "source").resolve(),
            (self.data_folder / ".chroma").resolve(),
            (self.data_folder / "skills").resolve(),
        ]
        
        self._read_write_paths = [
            (self.data_folder / "output").resolve(),
            (self.data_folder / "agent_tmp").resolve(),
            (self.data_folder / "sessions").resolve(),
        ]

    def _is_subpath(self, path: Path, parent: Path) -> bool:
        try:
            path.relative_to(parent)
            return True
        except ValueError:
            # Handle Windows/Unix case sensitivity or exact matches manually if needed
            return str(path) == str(parent) or str(path).startswith(str(parent) + os.sep)

    def check_read(self, file_path: str | Path) -> Path:
        """Check if reading from file_path is allowed. Returns resolved Path."""
        path = Path(file_path).resolve()
        
        # Must be inside data folder
        if not self._is_subpath(path, self.data_folder):
            raise SandboxViolationError(f"Access denied: {file_path} is outside the Data Folder.")
        
        # Determine if it is in an allowed subdirectory
        allowed = False
        for allowed_dir in self._read_only_paths + self._read_write_paths:
            if self._is_subpath(path, allowed_dir):
                allowed = True
                break
                
        if not allowed:
            raise SandboxViolationError(f"Access denied: Path {file_path} is not in an allowed Data Folder subdirectory.")
            
        return path

    def check_write(self, file_path: str | Path) -> Path:
        """Check if writing to file_path is allowed. Returns resolved Path."""
        path = Path(file_path).resolve()
        
        # Must be inside data folder
        if not self._is_subpath(path, self.data_folder):
            raise SandboxViolationError(f"Write denied: {file_path} is outside the Data Folder.")
            
        # Check if it's in a read-only path
        for ro_dir in self._read_only_paths:
            if self._is_subpath(path, ro_dir):
                raise SandboxViolationError(f"Write denied: {file_path} is in a read-only directory.")
                
        # Must be in a read-write path
        allowed = False
        for rw_dir in self._read_write_paths:
            if self._is_subpath(path, rw_dir):
                allowed = True
                break
                
        if not allowed:
            raise SandboxViolationError(f"Write denied: Path {file_path} is not in an allowed writable subdirectory.")
            
        return path
