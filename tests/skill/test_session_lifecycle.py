import shutil
from pathlib import Path
from kb_agent.skill.session import Session

def test_session_setup_and_cleanup(tmp_path):
    output_base = tmp_path / "output"
    python_base = tmp_path / "python"
    temp_base = tmp_path / "temp"
    
    session = Session()
    session.setup_dirs(output_base, python_base, temp_base)
    
    # Check if directories were created
    assert session.output_dir.exists()
    assert session.python_code_dir.exists()
    assert session.temp_dir.exists()
    
    run_id = session.run_id
    assert session.temp_dir == temp_base / run_id
    
    # Create some dummy files
    (session.python_code_dir / "script.py").write_text("print(1)")
    (session.temp_dir / "data.json").write_text("{}")
    (session.output_dir / "report.md").write_text("done")
    
    # Cleanup
    session.cleanup()
    
    # temp should be gone, python_code_dir is persisted for 24h
    assert session.python_code_dir.exists()
    assert not session.temp_dir.exists()
    
    # Output should remain
    assert session.output_dir.exists()
    assert (session.output_dir / "report.md").exists()

def test_session_to_dict():
    session = Session(run_id="test-run")
    p = Path("/tmp/test")
    session.output_dir = p / "out"
    session.python_code_dir = p / "py"
    session.temp_dir = p / "temp"
    
    d = session._to_dict()
    assert d["run_id"] == "test-run"
    assert d["temp_dir"] == str(p / "temp")
