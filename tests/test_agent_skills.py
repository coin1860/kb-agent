import os
import json
import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock
from kb_agent.agent_mode.skills import SkillLoader, SkillInfo

class MockSettings:
    def __init__(self, items):
        self.skills_path = items.get("skills_path")

@pytest.fixture
def mock_skills_env(tmp_path):
    skills_dir = tmp_path / "skills"
    skills_dir.mkdir()
    
    valid_skill = skills_dir / "my_skill.py"
    valid_skill.write_text("""\"\"\"
name: my_skill
description: does something
parameters: {"arg": "str"}
\"\"\"
def execute(arg):
    return {"status": "success", "result": "ok"}
""")

    invalid_skill = skills_dir / "bad_skill.py"
    invalid_skill.write_text("""
def execute(arg):
    pass
""")

    settings = MockSettings({"skills_path": str(skills_dir)})
    
    with patch("kb_agent.agent_mode.skills.settings", settings):
        yield skills_dir

def test_skill_loader_scan_and_manifest(mock_skills_env):
    loader = SkillLoader()
    loader.scan()
    
    assert "my_skill" in loader.skills
    assert "bad_skill" not in loader.skills
    
    info = loader.skills["my_skill"]
    assert info.name == "my_skill"
    assert info.description == "does something"
    assert info.parameters == {"arg": "str"}
    
    manifest_path = mock_skills_env / "__manifest__.json"
    assert manifest_path.exists()
    
    with open(manifest_path, "r") as f:
        manifest = json.load(f)
        names = [m["name"] for m in manifest]
        assert "my_skill" in names
        assert "bad_skill" not in names

def test_skill_invocation(mock_skills_env):
    loader = SkillLoader()
    loader.scan()
    
    mock_sandbox = "fake_sandbox"
    # execute doesn't accept sandbox in bad_skill but my_skill doesn't either, so it will not pass it (handled in invoke checking sig)
    res = loader.invoke("my_skill", {"arg": "val"}, sandbox=mock_sandbox)
    assert res == {"status": "success", "result": "ok"}

def test_builtin_skills_loading():
    # If skills_path is missing, should still load builtins
    with patch("kb_agent.agent_mode.skills.settings", None):
        loader = SkillLoader()
        loader.scan()
        assert "search_kb" in loader.skills
        assert "read_file" in loader.skills
        assert "write_output" in loader.skills
        assert "run_script" in loader.skills
        assert "ensure_venv" in loader.skills
