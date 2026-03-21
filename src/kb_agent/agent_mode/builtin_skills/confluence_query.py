"""
name: confluence_query
description: Fetches details for a specific Confluence page by ID.
parameters: {"page_id": "string"}
"""
from typing import Any

def execute(page_id: str, sandbox: Any = None) -> dict:
    try:
        from kb_agent.connectors.confluence import fetch_confluence_page
        result = fetch_confluence_page(page_id)
        if "Failed to fetch" in result or "not found" in result.lower():
            return {"status": "error", "result": result}
        return {"status": "success", "result": result}
    except Exception as e:
        return {"status": "error", "result": str(e)}
