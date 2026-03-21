"""
name: jira_query
description: Fetches details for a specific Jira ticket/issue by its ID.
parameters: {"issue_id": "string"}
"""
from typing import Any

def execute(issue_id: str, sandbox: Any = None) -> dict:
    try:
        from kb_agent.connectors.jira import fetch_jira_ticket
        result = fetch_jira_ticket(issue_id)
        if "Failed to fetch" in result or "not found" in result.lower():
            return {"status": "error", "result": result}
        return {"status": "success", "result": result}
    except Exception as e:
        return {"status": "error", "result": str(e)}
