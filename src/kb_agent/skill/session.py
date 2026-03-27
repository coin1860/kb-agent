"""
Session model for kb-cli execution lifecycle.

Designed for future multi-session persistence: all state lives in
the Session dataclass, nothing in module-level globals.
"""

from __future__ import annotations

import json
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional


@dataclass
class StepRecord:
    """Audit record for a single executed plan step."""
    step_number: int
    tool: str
    args: dict
    status: str  # done | failed | skipped | retried
    started_at: Optional[str] = None
    ended_at: Optional[str] = None
    result_summary: str = ""

    def to_dict(self) -> dict:
        return {
            "step_number": self.step_number,
            "tool": self.tool,
            "args": self.args,
            "status": self.status,
            "started_at": self.started_at,
            "ended_at": self.ended_at,
            "result_summary": self.result_summary,
        }


@dataclass
class Session:
    """
    Represents a single kb-cli REPL invocation.

    run_id is a UUID4. All paths are absolute. The manifest is written
    to output_dir/_manifest.json so each run is independently inspectable.
    This data model is designed so that future multi-session support can
    be added by implementing a session index without changing this schema.
    """
    run_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    started_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    skill_name: Optional[str] = None
    command: str = ""  # Original user command, used for LLM summary after Python execution
    status: str = "active"  # active | completed | aborted
    steps: list[StepRecord] = field(default_factory=list)
    output_dir: Optional[Path] = None
    python_code_dir: Optional[Path] = None
    temp_dir: Optional[Path] = None
    ended_at: Optional[str] = None

    def setup_dirs(self, output_base: Path, python_code_base: Path, temp_base: Optional[Path] = None) -> None:
        """Create run-scoped directories under output, python_code, and temp bases."""
        self.output_dir = output_base / self.run_id
        self.python_code_dir = python_code_base / self.run_id
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.python_code_dir.mkdir(parents=True, exist_ok=True)
        if temp_base is not None:
            self.temp_dir = temp_base / self.run_id
            self.temp_dir.mkdir(parents=True, exist_ok=True)

    def _manifest_path(self) -> Optional[Path]:
        if self.output_dir is None:
            return None
        return self.output_dir / "_manifest.json"

    def write_manifest(self) -> None:
        """Write the session manifest to output_dir/_manifest.json."""
        path = self._manifest_path()
        if path is None:
            return
        # Ensure the output directory exists (defensive: setup_dirs may not have been called)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(self._to_dict(), indent=2, ensure_ascii=False), encoding="utf-8")

    def update_manifest(self) -> None:
        """Alias for write_manifest — call after any state change."""
        self.write_manifest()

    def finish(self, status: str = "completed") -> None:
        """Mark session as finished and update manifest."""
        self.status = status
        self.ended_at = datetime.now(timezone.utc).isoformat()
        self.update_manifest()

    def add_step(self, record: StepRecord) -> None:
        """Append a step record and persist the manifest."""
        self.steps.append(record)
        self.update_manifest()

    def _to_dict(self) -> dict:
        return {
            "run_id": self.run_id,
            "started_at": self.started_at,
            "ended_at": self.ended_at,
            "skill_name": self.skill_name,
            "command": self.command,
            "status": self.status,
            "output_dir": str(self.output_dir) if self.output_dir else None,
            "python_code_dir": str(self.python_code_dir) if self.python_code_dir else None,
            "temp_dir": str(self.temp_dir) if self.temp_dir else None,
            "steps": [s.to_dict() for s in self.steps],
        }

    def cleanup(self) -> None:
        """Deep clean run-scoped temporary resources (specifically temp_dir).
        
        The python_code_dir is NOT cleaned here as it may contain scripts
        and logs the user wants to inspect. It is cleaned up via
        Session.garbage_collect() during CLI startup.
        """
        import shutil
        if self.temp_dir and self.temp_dir.exists():
            try:
                shutil.rmtree(self.temp_dir, ignore_errors=True)
            except Exception:
                pass

    @staticmethod
    def garbage_collect(base_path: Path, days: int = 1) -> int:
        """
        Find and remove run directories (UUID4 names) older than 'days'.
        
        Returns:
            The number of directories removed.
        """
        import shutil
        import time
        if not base_path.exists():
            return 0

        now = time.time()
        threshold = days * 86400  # seconds in a day
        removed_count = 0

        # Pattern for UUID4 names (e.g. b01fdd4c-0da0-40b4-b1a8-7a6f802ce6e7)
        uuid_pattern = r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$"
        import re

        for item in base_path.iterdir():
            if item.is_dir() and re.match(uuid_pattern, item.name):
                # Check modification time of the directory itself
                mtime = item.stat().st_mtime
                if (now - mtime) > threshold:
                    try:
                        shutil.rmtree(item, ignore_errors=True)
                        removed_count += 1
                    except Exception:
                        pass
        
        return removed_count
