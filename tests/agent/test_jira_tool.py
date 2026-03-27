import pytest
import json
from unittest.mock import MagicMock, patch
from kb_agent.agent.tools import jira_create_ticket
import kb_agent.config as config

@pytest.fixture
def mock_jira_connector():
    mock = MagicMock()
    return mock

def test_jira_tool_approval_yes(mock_jira_connector):
    # Success path: user says Y
    mock_jira_connector.create_issue.return_value = {"key": "KB-123", "url": "https://jira/KB-123"}
    
    mock_settings = MagicMock()
    mock_settings.jira_default_project = "KB"
    
    with patch("kb_agent.agent.tools._get_jira", return_value=mock_jira_connector):
        with patch("kb_agent.config.settings", mock_settings):
            # Mock rich console and panel to avoid printing artifacts in tests
            with patch("kb_agent.agent.tools.Console"), \
                 patch("kb_agent.agent.tools.Panel"), \
                 patch("kb_agent.agent.tools.input", return_value="y"):
                 
                 res_json = jira_create_ticket.func(summary="Test title")
                 res = json.loads(res_json)
                 
                 assert res["key"] == "KB-123"
                 mock_jira_connector.create_issue.assert_called_once_with(
                     project_key="KB",
                     summary="Test title",
                     description="",
                     issue_type="Task"
                 )

def test_jira_tool_approval_no(mock_jira_connector):
    # Cancel path: user says n
    mock_settings = MagicMock()
    mock_settings.jira_default_project = "KB"
    
    with patch("kb_agent.agent.tools._get_jira", return_value=mock_jira_connector):
        with patch("kb_agent.config.settings", mock_settings):
            with patch("kb_agent.agent.tools.Console"), \
                 patch("kb_agent.agent.tools.input", return_value="n"):
                 
                 res_json = jira_create_ticket.func(summary="Don't create me")
                 res = json.loads(res_json)
                 
                 assert res["status"] == "cancelled"
                 mock_jira_connector.create_issue.assert_not_called()

def test_jira_tool_missing_project(mock_jira_connector):
    # Error path: no project and no default
    mock_settings = MagicMock()
    mock_settings.jira_default_project = None
    
    with patch("kb_agent.agent.tools._get_jira", return_value=mock_jira_connector):
        with patch("kb_agent.config.settings", mock_settings):
            with patch("kb_agent.agent.tools.Console"), \
                 patch("kb_agent.agent.tools.input", return_value="y"):
                 
                 res_json = jira_create_ticket.func(summary="No proj", project_key="")
                 res = json.loads(res_json)
                 
                 assert res["status"] == "error"
                 assert "No project key provided" in res["message"]

def test_jira_tool_missing_summary(mock_jira_connector):
    mock_settings = MagicMock()
    mock_settings.jira_default_project = "KB"
    
    with patch("kb_agent.agent.tools._get_jira", return_value=mock_jira_connector):
        with patch("kb_agent.config.settings", mock_settings):
            with patch("kb_agent.agent.tools.Console"):
                 res_json = jira_create_ticket.func(summary="", project_key="KB")
                 res = json.loads(res_json)
                 assert res["status"] == "error"
                 assert "Summary is required" in res["message"]
                 mock_jira_connector.create_issue.assert_not_called()
