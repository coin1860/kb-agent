import os
import json
import pytest
from unittest.mock import patch, MagicMock
from pathlib import Path
from pydantic import SecretStr

# Import before config is loaded to ensure we mock it
import kb_agent.config as config

@pytest.fixture
def mock_config_paths(tmp_path):
    """Fixture to mock paths so we don't mess with ~/.kb-agent."""
    config_dir = tmp_path / ".kb-agent-test"
    config_file = config_dir / "kb-agent.json"
    old_env = tmp_path / ".kb_agent-old" / ".env"
    local_env = tmp_path / "local.env"
    
    with patch("kb_agent.config.CONFIG_DIR", config_dir), \
         patch("kb_agent.config.CONFIG_FILE", config_file), \
         patch("kb_agent.config.OLD_ENV_FILE", old_env), \
         patch("kb_agent.config.LOCAL_ENV_FILE", local_env):
        yield config_dir, config_file, old_env

def test_initial_load_creates_json_with_defaults(mock_config_paths):
    config_dir, config_file, old_env = mock_config_paths
    
    # Ensure nothing exists
    assert not config_file.exists()
    
    # Reload settings
    settings = config.load_settings()
    
    assert config_file.exists()
    assert settings is not None
    assert settings.llm_model is None
    assert settings.llm_api_key is None
    
    with open(config_file, "r") as f:
        data = json.load(f)
        assert "llm_model" not in data or data.get("llm_model") is None
        assert "llm_api_key" not in data

def test_initial_load_with_old_env(mock_config_paths):
    config_dir, config_file, old_env = mock_config_paths
    
    # Create old env file
    old_env.parent.mkdir(parents=True)
    old_env.write_text('KB_AGENT_LLM_API_KEY="test-key"\nKB_AGENT_LLM_MODEL="custom-model"')
    
    # Reload settings
    settings = config.load_settings()
    
    assert config_file.exists()
    assert settings.llm_api_key.get_secret_value() == "test-key"
    assert settings.llm_model == "custom-model"
    # Null out defaults since DEFAULTS was removed
    assert settings.embedding_model is None

def test_save_settings(mock_config_paths):
    config_dir, config_file, old_env = mock_config_paths
    
    settings = config.load_settings()
    settings.llm_model = "gpt-4o"
    settings.llm_api_key = SecretStr("secret-123")
    
    config.save_settings(settings)
    
    with open(config_file, "r") as f:
        data = json.load(f)
        assert data["llm_model"] == "gpt-4o"
        assert data["llm_api_key"] == "secret-123"

def test_update_setting(mock_config_paths):
    config_dir, config_file, old_env = mock_config_paths
    
    config.load_settings()
    config.update_setting("llm_model", "claude-3")
    
    with open(config_file, "r") as f:
        data = json.load(f)
        assert data["llm_model"] == "claude-3"
        
    assert config.settings.llm_model == "claude-3"
