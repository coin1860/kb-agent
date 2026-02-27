"""Pytest configuration to handle macOS permission issues."""
import os
import stat

# Paths that may have macOS TCC/quarantine restrictions
_PROBLEM_PATHS = [".env", "audit.log"]

def pytest_ignore_collect(collection_path, config):
    """Skip paths that have permission issues on macOS."""
    name = os.path.basename(str(collection_path))
    if name in _PROBLEM_PATHS:
        return True

    try:
        collection_path.stat()
    except PermissionError:
        return True

    return None
