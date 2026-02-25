import requests
import os
from typing import List, Dict, Any, Optional
from .base import BaseConnector
import kb_agent.config as config

class JiraConnector(BaseConnector):
    """
    Connector for fetching Jira issues.
    """
    def __init__(self, base_url: str = None, api_key: str = None):
        settings = config.settings
        self.base_url = base_url or (str(settings.jira_url) if settings and settings.jira_url else "https://jira.example.com")
        self.api_key = api_key or os.getenv("JIRA_API_KEY")

    def fetch_data(self, query: str) -> List[Dict[str, Any]]:
        """
        Fetches a specific Jira issue by key (e.g., "PROJ-123").
        """
        if not self.api_key:
             # In a real scenario, raise or log warning. For this demo, maybe return mock data?
             print("Jira API Key not set. Returning mock data.")
             return self._mock_data(query)

        url = f"{self.base_url}/rest/api/2/issue/{query}"
        try:
            response = requests.get(url, auth=("user", self.api_key))
            if response.status_code == 200:
                data = response.json()
                return [{
                    "id": data["key"],
                    "title": data["fields"]["summary"],
                    "content": data["fields"]["description"], # Basic description
                    "metadata": {
                        "source": "jira",
                        "status": data["fields"]["status"]["name"],
                        "priority": data["fields"]["priority"]["name"]
                    }
                }]
            else:
                print(f"Failed to fetch Jira issue {query}: {response.status_code}")
                return []
        except Exception as e:
            print(f"Error fetching form Jira: {e}")
            return []

    def fetch_all(self) -> List[Dict[str, Any]]:
        # fetching ALL Jira issues is generally not feasible without specific JQL.
        # Maybe fetch recent issues?
        return []

    def _mock_data(self, issue_key: str) -> List[Dict[str, Any]]:
        return [{
            "id": issue_key,
            "title": f"Mock Issue {issue_key}",
            "content": f"This is a mock description for Jira issue {issue_key}.\n\nIt involves updating the login flow.",
            "metadata": {"source": "jira", "status": "Open", "priority": "High"}
        }]
