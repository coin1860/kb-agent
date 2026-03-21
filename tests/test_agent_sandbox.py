import pytest
from pathlib import Path
from unittest.mock import patch
from kb_agent.agent_mode.sandbox import SandboxContext, SandboxViolationError

@pytest.fixture
def mock_settings(tmp_path):
    test_data_dir = tmp_path / "data"
    test_data_dir.mkdir()
    (test_data_dir / "skills").mkdir()
    (test_data_dir / "index").mkdir()
    (test_data_dir / "output").mkdir()
    (test_data_dir / "agent_tmp").mkdir()
    
    class MockSettings:
        def __init__(self):
            self.data_folder = str(test_data_dir)
            
    with patch("kb_agent.agent_mode.sandbox.settings", MockSettings()):
        yield test_data_dir

def test_sandbox_allowed_read(mock_settings):
    ctx = SandboxContext("test-session")
    
    allowed_file = mock_settings / "skills" / "test.py"
    allowed_file.touch()
    
    resolved = ctx.check_read(allowed_file)
    assert resolved == allowed_file.resolve()
    
def test_sandbox_denied_read_outside(mock_settings):
    ctx = SandboxContext("test-session")
    
    outside_file = mock_settings.parent / "outside.txt"
    outside_file.touch()
    
    with pytest.raises(SandboxViolationError, match="outside the Data Folder"):
        ctx.check_read(outside_file)

def test_sandbox_denied_read_unauthorized_subdir(mock_settings):
    ctx = SandboxContext("test-session")
    
    unauth_dir = mock_settings / "private"
    unauth_dir.mkdir()
    unauth_file = unauth_dir / "secret.txt"
    unauth_file.touch()
    
    with pytest.raises(SandboxViolationError, match="not in an allowed Data Folder subdirectory"):
        ctx.check_read(unauth_file)

def test_sandbox_allowed_write(mock_settings):
    ctx = SandboxContext("test-session")
    
    output_file = mock_settings / "output" / "result.txt"
    resolved = ctx.check_write(output_file)
    assert resolved == output_file.resolve()

def test_sandbox_denied_write_read_only(mock_settings):
    ctx = SandboxContext("test-session")
    
    ro_file = mock_settings / "index" / "data.idx"
    
    with pytest.raises(SandboxViolationError, match="in a read-only directory"):
        ctx.check_write(ro_file)
        
def test_sandbox_path_traversal(mock_settings):
    ctx = SandboxContext("test-session")
    
    traversal_path = mock_settings / "output" / ".." / ".." / "system.cfg"
    
    with pytest.raises(SandboxViolationError, match="outside the Data Folder"):
        ctx.check_read(traversal_path)
