import pytest
from pathlib import Path
from unittest.mock import MagicMock, patch
from kb_agent.tools.file_tool import FileTool
import kb_agent.config as config

@pytest.fixture
def mock_settings(tmp_path):
    # Setup a mock data folder structure
    data_folder = tmp_path / "data"
    temp_path = data_folder / "temp"
    output_path = data_folder / "output"
    input_path = data_folder / "input"
    source_path = data_folder / "source"
    index_path = data_folder / "index"
    
    for d in [temp_path, output_path, input_path, source_path, index_path]:
        d.mkdir(parents=True, exist_ok=True)
        
    s = MagicMock()
    s.data_folder = data_folder
    s.temp_path = temp_path
    s.output_path = output_path
    s.input_path = input_path
    s.source_docs_path = source_path
    s.index_path = index_path
    return s

def test_file_tool_fallback(mock_settings):
    with patch("kb_agent.config.settings", mock_settings):
        tool = FileTool()
        
        # 1. Test fallback to temp/ (priority 1)
        temp_file = mock_settings.temp_path / "run123" / "analysis.json"
        temp_file.parent.mkdir(parents=True, exist_ok=True)
        temp_file.write_text("{\"status\": \"temp\"}")
        
        content = tool.read_file("analysis.json")
        assert content == "{\"status\": \"temp\"}"
        
        # 2. Test fallback to output/ (priority 2)
        output_file = mock_settings.output_path / "run456" / "report.md"
        output_file.parent.mkdir(parents=True, exist_ok=True)
        output_file.write_text("# Final Report")
        
        content = tool.read_file("report.md")
        assert content == "# Final Report"

        # 3. Test mtime priority (newer file should be returned)
        import time
        new_temp = mock_settings.temp_path / "run789" / "data.csv"
        new_temp.parent.mkdir(parents=True, exist_ok=True)
        new_temp.write_text("v2")
        
        old_temp = mock_settings.temp_path / "run000" / "data.csv"
        old_temp.parent.mkdir(parents=True, exist_ok=True)
        old_temp.write_text("v1")
        # Ensure mtime is different
        os_path_old = str(old_temp)
        os_path_new = str(new_temp)
        import os
        os.utime(os_path_old, (time.time() - 100, time.time() - 100))
        os.utime(os_path_new, (time.time(), time.time()))

        content = tool.read_file("data.csv")
        assert content == "v2"

def test_file_tool_allowed_paths(mock_settings):
    with patch("kb_agent.config.settings", mock_settings):
        tool = FileTool()
        # Verify output and temp are in allowed_paths
        allowed_str = [str(p) for p in tool.allowed_paths]
        assert str(mock_settings.output_path.resolve()) in allowed_str
        assert str(mock_settings.temp_path.resolve()) in allowed_str
