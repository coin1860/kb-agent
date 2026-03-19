import pytest
from unittest.mock import MagicMock, patch
from kb_agent.connectors.jira import JiraConnector
from kb_agent.connectors.confluence import ConfluenceConnector

@patch("kb_agent.connectors.jira.Jira")
@patch("kb_agent.config.settings")
def test_jira_connector_get_issue(mock_settings, mock_jira_class):
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

@patch("kb_agent.connectors.confluence.Confluence")
@patch("kb_agent.config.settings")
def test_confluence_connector_get_page(mock_settings, mock_conf_class):
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
