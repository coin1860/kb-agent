import pytest
from unittest.mock import patch
import os
import kb_agent.config
from kb_agent.llm import LLMClient

# Fixture to mock settings for each test
@pytest.fixture
def mock_settings():
    with patch("kb_agent.config.settings") as mock:
        mock.llm_api_key.get_secret_value.return_value = "dummy_key"
        mock.llm_base_url = "http://dummy.url"
        yield mock

def test_sanitize_groq_com_prefix(mock_settings):
    """Test that 'groq-com/' prefix is removed."""
    mock_settings.llm_model = "groq-com/llama-3.3-70b-versatile"

    # Re-instantiate LLMClient to pick up new settings
    client = LLMClient()

    assert client.model == "llama-3.3-70b-versatile"

def test_sanitize_groq_prefix(mock_settings):
    """Test that 'groq/' prefix is removed."""
    mock_settings.llm_model = "groq/llama-3.3-70b-versatile"

    client = LLMClient()

    assert client.model == "llama-3.3-70b-versatile"

def test_no_change_standard_model(mock_settings):
    """Test that standard model names are unchanged."""
    mock_settings.llm_model = "gpt-4"

    client = LLMClient()

    assert client.model == "gpt-4"

def test_no_change_no_prefix_llama(mock_settings):
    """Test that a llama model without prefix is unchanged."""
    mock_settings.llm_model = "llama-3.3-70b-versatile"

    client = LLMClient()

    assert client.model == "llama-3.3-70b-versatile"
