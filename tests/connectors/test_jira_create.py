import pytest
from unittest.mock import MagicMock, patch
from kb_agent.connectors.jira import JiraConnector
import kb_agent.config as config

@pytest.fixture
def mock_jira():
    mock_lib = MagicMock()
    mock_connector = JiraConnector()
    mock_connector.jira = mock_lib
    mock_connector.base_url = "https://jira.test"
    mock_connector.token = "fake-token"
    return mock_connector, mock_lib

def test_jira_create_issue_success(mock_jira):
    connector, lib = mock_jira
    lib.create_issue.return_value = {"key": "KB-123"}
    
    res = connector.create_issue(
        project_key="KB",
        summary="Test Summary",
        description="Test Desc",
        issue_type="Bug"
    )
    
    assert res["key"] == "KB-123"
    assert res["url"] == "https://jira.test/browse/KB-123"
    assert res["project"] == "KB"
    
    # Check calls
    lib.create_issue.assert_called_once()
    fields = lib.create_issue.call_args[1]["fields"]
    assert fields["project"]["key"] == "KB"
    assert fields["summary"] == "Test Summary"
    assert fields["issuetype"]["name"] == "Bug"
    assert fields["description"] == "Test Desc"

def test_jira_create_issue_default_project(mock_jira):
    connector, lib = mock_jira
    lib.create_issue.return_value = {"key": "DEF-456"}
    
    mock_settings = MagicMock()
    mock_settings.jira_default_project = "DEF"
    
    with patch("kb_agent.config.settings", mock_settings):
        # Empty project key should use default
        res = connector.create_issue(
            project_key="",
            summary="Default Proj Test"
        )
        assert res["project"] == "DEF"
        assert res["key"] == "DEF-456"

def test_jira_create_issue_error_no_project(mock_jira):
    connector, lib = mock_jira
    
    mock_settings = MagicMock()
    mock_settings.jira_default_project = None
    
    with patch("kb_agent.config.settings", mock_settings):
        # No project key and no default project should error
        res = connector.create_issue(
            project_key="",
            summary="Bad request"
        )
        assert res["error"] is True
        assert "No project key provided" in res["content"]

def test_jira_create_issue_api_failure(mock_jira):
    connector, lib = mock_jira
    lib.create_issue.side_effect = Exception("API Unavailable")
    
    res = connector.create_issue(
        project_key="KB",
        summary="Fail test"
    )
    assert res["error"] is True
    assert "Failed to create Jira issue" in res["content"]
