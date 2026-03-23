import json
import pytest
from pathlib import Path
from unittest.mock import patch
from kb_agent.connectors.cache import APICache

@pytest.fixture
def mock_cache_path(tmp_path):
    with patch("kb_agent.connectors.cache.config.settings") as mock_settings:
        mock_settings.cache_path = tmp_path
        yield tmp_path

def test_cache_initialization(mock_cache_path):
    cache = APICache()
    assert cache.cache_root == mock_cache_path

def test_cache_miss(mock_cache_path):
    cache = APICache()
    result = cache.read("jira", "TEST-1")
    assert result is None

def test_cache_write_and_read(mock_cache_path):
    cache = APICache()
    test_data = {"id": "TEST-1", "title": "Test Title", "content": "Test content"}
    
    # Write to cache
    cache.write("jira", "TEST-1", test_data)
    
    # Read back
    result = cache.read("jira", "TEST-1")
    assert result == test_data
    
    # Verify file system
    main_file = mock_cache_path / "jira" / "TEST-1" / "main.json"
    assert main_file.exists()
    with open(main_file, "r", encoding="utf-8") as f:
        saved_data = json.load(f)
    assert saved_data == test_data

