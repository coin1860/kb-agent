import logging
import json
import os
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional

# Try to import settings, but handle the case where it fails due to missing env vars
try:
    from kb_agent.config import settings
    LOG_FILE = settings.audit_log_path if settings else Path("audit.log")
except Exception:
    LOG_FILE = Path("audit.log")

# Configure the logger
logger = logging.getLogger("kb_agent_audit")
logger.setLevel(logging.INFO)

# File handler
handler = logging.FileHandler(LOG_FILE, encoding='utf-8')
formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
handler.setFormatter(formatter)
logger.addHandler(handler)

def log_audit(action: str, details: Dict[str, Any]):
    """
    Logs an audit event.

    Args:
        action (str): The type of action (e.g., "search_query", "tool_call", "llm_response").
        details (Dict[str, Any]): The details of the action.
    """
    try:
        log_entry = {
            "timestamp": datetime.now().isoformat(),
            "action": action,
            "details": details
        }
        logger.info(json.dumps(log_entry, ensure_ascii=False))
    except Exception as e:
        # Fallback to simple print if logging fails, though unlikely
        print(f"Failed to log audit: {e}")

def log_search(query: str, results_count: int, sources: list[str]):
    """Convenience function for logging search actions."""
    log_audit("search_query", {
        "query": query,
        "results_count": results_count,
        "sources": sources
    })

def log_tool_use(tool_name: str, input_args: Dict[str, Any], output: Any):
    """Convenience function for logging tool usage."""
    # Truncate output if it's too long
    output_str = str(output)
    if len(output_str) > 500:
        output_str = output_str[:500] + "... (truncated)"

    log_audit("tool_use", {
        "tool_name": tool_name,
        "input": input_args,
        "output": output_str
    })

def log_llm_response(prompt: str, response: str):
    """Convenience function for logging LLM interactions."""
    log_audit("llm_interaction", {
        "prompt_summary": prompt[:100] + "..." if len(prompt) > 100 else prompt,
        "response_summary": response[:100] + "..." if len(response) > 100 else response,
        "full_response_length": len(response)
    })
