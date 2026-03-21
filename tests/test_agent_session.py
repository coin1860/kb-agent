import pytest
from pathlib import Path
from unittest.mock import patch
from kb_agent.agent_mode.session import SessionManager, Session

@pytest.fixture
def mock_session_settings(tmp_path):
    test_data_dir = tmp_path / "data"
    test_data_dir.mkdir()
    
    class MockSettings:
        def __init__(self):
            self.data_folder = str(test_data_dir)
            
    with patch("kb_agent.agent_mode.session.settings", MockSettings()):
        yield test_data_dir

def test_session_create_and_list(mock_session_settings):
    manager = SessionManager()
    
    session = manager.create("Find all python files")
    assert session.goal == "Find all python files"
    assert session.status == "init"
    assert manager.active_session_id == session.id
    
    sessions = manager.list_all()
    assert len(sessions) == 1
    assert sessions[0].id == session.id
    
    session2 = manager.create("Do something else")
    sessions = manager.list_all()
    assert len(sessions) == 2

def test_session_checkpoint_and_resume(mock_session_settings):
    manager = SessionManager()
    session = manager.create("Goal 1")
    
    state = {
        "session_id": session.id,
        "goal": "Goal 1",
        "task_status": "running",
        "plan": [{"status": "pending"}]
    }
    
    manager.checkpoint(session.id, state)
    
    # Resume
    manager2 = SessionManager()
    resumed_state = manager2.resume(session.id)
    
    assert resumed_state["task_status"] == "running"
    assert resumed_state["plan"] == [{"status": "pending"}]
    assert manager2.active_session_id == session.id

def test_session_switch(mock_session_settings):
    manager = SessionManager()
    s1 = manager.create("G1")
    s2 = manager.create("G2")
    
    assert manager.active_session_id == s2.id
    
    manager.switch_to(s1.id)
    assert manager.active_session_id == s1.id
