import json
import uuid
import datetime
from pathlib import Path
from dataclasses import dataclass, asdict
from typing import Dict, Any, List, Optional
from kb_agent.config import settings

@dataclass
class Session:
    id: str
    goal: str
    status: str
    created_at: str
    updated_at: str
    plan: List[Dict[str, Any]]
    checkpoint: Optional[Dict[str, Any]] = None

class SessionManager:
    def __init__(self):
        if not settings or not settings.data_folder:
            self.sessions_dir = None
            self.agent_tmp_dir = None
        else:
            data_folder = Path(settings.data_folder)
            self.sessions_dir = data_folder / "sessions"
            self.agent_tmp_dir = data_folder / "agent_tmp"
            
            try:
                self.sessions_dir.mkdir(parents=True, exist_ok=True)
                self.agent_tmp_dir.mkdir(parents=True, exist_ok=True)
            except Exception:
                pass
                
        self.active_session_id: Optional[str] = None
        
    def _get_session_file(self, session_id: str) -> Path:
        if not self.sessions_dir:
            raise ValueError("Data folder is not configured")
        return self.sessions_dir / f"{session_id}.json"
        
    def create(self, goal: str) -> Session:
        session_id = str(uuid.uuid4())
        if self.agent_tmp_dir:
            workspace = self.agent_tmp_dir / session_id
            workspace.mkdir(parents=True, exist_ok=True)
            (workspace / "scripts").mkdir(exist_ok=True)
            (workspace / "drafts").mkdir(exist_ok=True)
        
        now = datetime.datetime.now().isoformat()
        session = Session(
            id=session_id,
            goal=goal,
            status="init",
            created_at=now,
            updated_at=now,
            plan=[],
            checkpoint=None
        )
        self._save(session)
        self.active_session_id = session_id
        return session
        
    def list_all(self) -> List[Session]:
        if not self.sessions_dir or not self.sessions_dir.exists():
            return []
            
        sessions = []
        for file in self.sessions_dir.glob("*.json"):
            try:
                with open(file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    sessions.append(Session(**data))
            except Exception:
                pass
        return sorted(sessions, key=lambda s: s.updated_at, reverse=True)
        
    def get(self, session_id: str) -> Optional[Session]:
        if not self.sessions_dir:
            return None
        file_path = self._get_session_file(session_id)
        if not file_path.exists():
            return None
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                return Session(**data)
        except Exception:
            return None
            
    def switch_to(self, session_id: str) -> Session:
        session = self.get(session_id)
        if not session:
            raise ValueError(f"Session {session_id} not found")
        self.active_session_id = session_id
        return session
        
    def checkpoint(self, session_id: str, state: Dict[str, Any]):
        session = self.get(session_id)
        if not session:
            raise ValueError(f"Session {session_id} not found")
            
        session.updated_at = datetime.datetime.now().isoformat()
        session.status = state.get("task_status", session.status)
        session.plan = state.get("plan", session.plan)
        
        session.checkpoint = state
        self._save(session)
        
    def _save(self, session: Session):
        if not self.sessions_dir:
            return
        file_path = self._get_session_file(session.id)
        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(asdict(session), f, indent=2)
            
    def resume(self, session_id: str) -> Dict[str, Any]:
        """Returns the State dictionary to resume computation."""
        session = self.get(session_id)
        if not session:
            raise ValueError(f"Session {session_id} not found")
        if not session.checkpoint:
            raise ValueError(f"Session {session_id} has no checkpoint state")
        self.active_session_id = session_id
        return session.checkpoint
