import pytest
from unittest.mock import MagicMock, patch
from kb_agent.connectors.jira import JiraConnector
from kb_agent.connectors.confluence import ConfluenceConnector
from kb_agent.connectors.cache import APICache

@patch("kb_agent.connectors.jira.Jira")
@patch("kb_agent.config.settings")
@patch.object(APICache, "read", return_value=None)
@patch.object(APICache, "write")
def test_jira_connector_get_issue(mock_write, mock_read, mock_settings, mock_jira_class):
    mock_settings.jira_url = "http://jira.test"
    mock_settings.jira_token.get_secret_value.return_value = "test-token"
    
    # Setup mock jira instance
    mock_jira_inst = MagicMock()
    mock_jira_class.return_value = mock_jira_inst
    
    mock_jira_inst.issue.return_value = {
        "key": "PROJ-123",
        "fields": {
            "summary": "Test Issue",
            "status": {"name": "Open"},
            "description": "Some description",
            "issuetype": {"name": "Bug"},
            "priority": {"name": "High"},
            "assignee": {"displayName": "User A"},
            "reporter": {"displayName": "User B"},
            "created": "2023-01-01",
            "updated": "2023-01-02"
        }
    }
    
    
    connector = JiraConnector()
    issue = connector.get_issue("PROJ-123")
    
    assert issue is not None
    assert issue["id"] == "PROJ-123"
    assert issue["title"] == "Test Issue"
    assert "PROJ-123" in issue["content"]
    assert "Some description" in issue["content"]
    
    mock_read.assert_called_once_with("jira", "PROJ-123")
    mock_write.assert_called_once()
    assert mock_write.call_args[0][0] == "jira"
    assert mock_write.call_args[0][1] == "PROJ-123"

@patch("kb_agent.connectors.confluence.Confluence")
@patch("kb_agent.config.settings")
@patch.object(APICache, "read", return_value=None)
@patch.object(APICache, "write")
def test_confluence_connector_get_page(mock_write, mock_read, mock_settings, mock_conf_class):
    mock_settings.confluence_url = "http://conf.test"
    mock_settings.confluence_token.get_secret_value.return_value = "test-token"
    
    # Setup mock confluence instance
    mock_conf_inst = MagicMock()
    mock_conf_class.return_value = mock_conf_inst
    
    mock_conf_inst.get_page_by_id.return_value = {
        "id": "12345",
        "title": "Test Page",
        "body": {"storage": {"value": "<p>Hello World</p>"}},
        "space": {"name": "Test Space"},
        "version": {"number": 1},
        "ancestors": []
    }
    
    connector = ConfluenceConnector()
    page = connector.get_page("12345")
    
    assert page is not None
    assert page["id"] == "12345"
    assert page["title"] == "Test Page"
    assert "Hello World" in page["content"]
    
    mock_read.assert_called_once_with("confluence", "12345")
    mock_write.assert_called_once()
    assert mock_write.call_args[0][0] == "confluence"
    assert mock_write.call_args[0][1] == "12345"

@patch("kb_agent.connectors.jira.Jira")
@patch("kb_agent.config.settings")
@patch.object(APICache, "read", return_value=None)
@patch.object(APICache, "write")
def test_jira_connector_force_refresh(mock_write, mock_read, mock_settings, mock_jira_class):
    mock_settings.jira_url = "http://jira.test"
    mock_settings.jira_token.get_secret_value.return_value = "test-token"
    mock_jira_inst = MagicMock()
    mock_jira_class.return_value = mock_jira_inst
    mock_jira_inst.issue.return_value = {"key": "PROJ-123", "fields": {"summary": "Test Issue"}}
    
    connector = JiraConnector()
    issue = connector.get_issue("PROJ-123", force_refresh=True)
    
    assert issue is not None
    mock_read.assert_not_called()
    mock_write.assert_called_once_with("jira", "PROJ-123", issue)

@patch("kb_agent.connectors.confluence.Confluence")
@patch("kb_agent.config.settings")
@patch.object(APICache, "read", return_value=None)
@patch.object(APICache, "write")
def test_confluence_connector_force_refresh(mock_write, mock_read, mock_settings, mock_conf_class):
    mock_settings.confluence_url = "http://conf.test"
    mock_settings.confluence_token.get_secret_value.return_value = "test-token"
    mock_conf_inst = MagicMock()
    mock_conf_class.return_value = mock_conf_inst
    mock_conf_inst.get_page_by_id.return_value = {"id": "12345", "title": "Test Page", "body": {"storage": {"value": ""}}, "space": {"name": ""}, "version": {"number": 1}, "ancestors": []}
    
    connector = ConfluenceConnector()
    page = connector.get_page("12345", force_refresh=True)
    
    assert page is not None
    mock_read.assert_not_called()
    mock_write.assert_called_once_with("confluence", "12345", page)

@patch("kb_agent.config.settings")
def test_jira_not_configured(mock_settings):
    mock_settings.jira_url = None
    connector = JiraConnector()
    issue = connector.get_issue("ABC-123")
    assert issue is not None
    assert issue["metadata"]["error"] is True
    assert "not configured" in issue["title"].lower()

@patch("kb_agent.config.settings")
def test_confluence_not_configured(mock_settings):
    mock_settings.confluence_url = None
    connector = ConfluenceConnector()
    page = connector.get_page("12345")
    assert page is not None
    assert page["metadata"]["error"] is True
    assert "not configured" in page["title"].lower()
