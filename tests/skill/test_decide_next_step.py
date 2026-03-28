"""
Unit tests for the dynamic decision loop helpers in skill/planner.py:
  - decide_next_step()
  - preview_intent()
  - _build_tool_history_str()
"""

import json
from pathlib import Path
from unittest.mock import MagicMock

import pytest


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

def _make_llm(content: str = "", tool_calls=None):
    """Create a mock LLM that returns fixed content."""
    llm = MagicMock()
    msg = MagicMock()
    msg.content = content
    msg.tool_calls = tool_calls or []
    
    llm.invoke.return_value = msg
    bound_llm = MagicMock()
    bound_llm.invoke.return_value = msg
    llm.bind_tools.return_value = bound_llm
    return llm


def _make_session():
    """Return a minimal mock Session."""
    session = MagicMock()
    session.run_id = "test-run-123"
    return session


def _make_skill_def(name="test-skill", raw="step 1: fetch\nstep 2: write_file with result"):
    """Return a minimal mock SkillDef."""
    from kb_agent.skill.loader import SkillDef
    return SkillDef(
        name=name,
        description="Test skill for unit testing",
        file_path=Path(f"{name}.yaml"),
        raw_content=raw,
    )


# ─────────────────────────────────────────────────────────────────────────────
# decide_next_step — call_tool path
# ─────────────────────────────────────────────────────────────────────────────

def test_decide_returns_call_tool():
    """When LLM returns call_tool JSON, decide_next_step parses it correctly."""
    from kb_agent.skill.planner import decide_next_step

    tool_calls = [{"name": "jira_fetch", "args": {"issue_key": "PROJ-1"}, "id": "call_123"}]
    llm = _make_llm(content="fetch ticket", tool_calls=tool_calls)
    session = _make_session()

    result = decide_next_step("fetch PROJ-1", session, llm)

    assert result["action"] == "call_tool"
    assert result["tool"] == "jira_fetch"
    assert result["args"] == {"issue_key": "PROJ-1"}
    assert result["reason"] == "fetch ticket"


def test_decide_returns_final_answer():
    """When LLM returns final_answer JSON, decide_next_step parses it correctly."""
    from kb_agent.skill.planner import decide_next_step

    tool_calls = [{"name": "direct_response", "args": {"answer": "The ticket status is Done."}, "id": "call_456"}]
    llm = _make_llm(tool_calls=tool_calls)
    session = _make_session()

    result = decide_next_step("what is the status of PROJ-1?", session, llm, tool_history=[
        {"step": 1, "tool": "jira_fetch", "args": {"issue_key": "PROJ-1"}, "result": "Status: Done", "status": "success"}
    ])

    assert result["action"] == "final_answer"
    assert result["answer"] == "The ticket status is Done."


# ─────────────────────────────────────────────────────────────────────────────
# decide_next_step — max_iterations guard
# ─────────────────────────────────────────────────────────────────────────────

def test_decide_max_iterations_forces_final_in_prompt():
    """When iteration >= max_iterations, the MAX ITERATIONS warning appears in the prompt."""
    from kb_agent.skill.planner import decide_next_step

    tool_calls = [{"name": "direct_response", "args": {"answer": "Partial answer."}, "id": "call_789"}]
    llm = _make_llm(tool_calls=tool_calls)
    session = _make_session()

    result = decide_next_step("do something", session, llm, iteration=3, max_iterations=3)

    # Check LLM was called via bind_tools
    llm.bind_tools.return_value.invoke.assert_called_once()
    # Find the user message content
    call_args = llm.bind_tools.return_value.invoke.call_args[0][0]  # messages list
    user_msg_content = call_args[-1].content  # HumanMessage info at the end
    assert "MAX ITERATIONS REACHED" in user_msg_content
    assert result["action"] == "final_answer"


def test_decide_empty_tool_history():
    """First call with no tool history should work without errors."""
    from kb_agent.skill.planner import decide_next_step

    tool_calls = [{"name": "vector_search", "args": {"query": "hello"}, "id": "call_abc"}]
    llm = _make_llm(content="first search", tool_calls=tool_calls)
    session = _make_session()

    result = decide_next_step("search for hello", session, llm)

    assert result["action"] == "call_tool"
    assert result["tool"] == "vector_search"
    llm.bind_tools.return_value.invoke.assert_called_once()


# ─────────────────────────────────────────────────────────────────────────────
# decide_next_step — skill playbook hard constraint
# ─────────────────────────────────────────────────────────────────────────────

def test_decide_skill_hard_constraint_appears_in_prompt():
    """When skill_def is provided, its playbook content appears in the LLM prompt."""
    from kb_agent.skill.planner import decide_next_step

    tool_calls = [{"name": "jira_jql", "args": {"query": "weekly report"}, "id": "call_def"}]
    llm = _make_llm(content="step 1", tool_calls=tool_calls)
    session = _make_session()
    skill = _make_skill_def(name="weekly-report", raw="step 1: jira_jql query weekly\nstep 2: write_file report")

    result = decide_next_step("generate weekly report", session, llm, skill_def=skill)

    llm.bind_tools.return_value.invoke.assert_called_once()
    call_args = llm.bind_tools.return_value.invoke.call_args[0][0]
    user_msg_content = call_args[1].content
    # Playbook content and constraint marker should be in the prompt
    assert "SKILL PLAYBOOK HARD CONSTRAINT" in user_msg_content
    assert "weekly-report" in user_msg_content


# ─────────────────────────────────────────────────────────────────────────────
# decide_next_step — LLM failure fallback
# ─────────────────────────────────────────────────────────────────────────────

def test_decide_llm_failure_returns_final_answer():
    """If LLM raises an exception, decide_next_step falls back to final_answer with error msg."""
    from kb_agent.skill.planner import decide_next_step

    llm = MagicMock()
    bound_llm = MagicMock()
    bound_llm.invoke.side_effect = Exception("connection error")
    llm.bind_tools.return_value = bound_llm
    session = _make_session()

    result = decide_next_step("do something", session, llm)

    assert result["action"] == "final_answer"
    assert "error" in result["answer"].lower()


def test_decide_no_tool_calls_returns_final_answer():
    """If LLM returns text with no tool calls, treat as final answer."""
    from kb_agent.skill.planner import decide_next_step

    llm = _make_llm(content="Here is some text")
    session = _make_session()

    result = decide_next_step("do something", session, llm)

    assert result["action"] == "final_answer"
    assert result["answer"] == "Here is some text"


# ─────────────────────────────────────────────────────────────────────────────
# decide_next_step — fenced JSON parsing
# ─────────────────────────────────────────────────────────────────────────────




# ─────────────────────────────────────────────────────────────────────────────
# preview_intent — skill path (no LLM call)
# ─────────────────────────────────────────────────────────────────────────────

def test_preview_intent_skill_no_llm_call():
    """preview_intent with a skill_def should NOT call the LLM."""
    from kb_agent.skill.planner import preview_intent

    llm = MagicMock()
    skill = _make_skill_def(raw="step 1: jira_fetch\nstep 2: write_file report")

    result = preview_intent("generate report", skill_def=skill, llm=llm)

    llm.invoke.assert_not_called()
    assert "summary" in result
    assert isinstance(result["has_write_ops"], bool)
    assert result["has_write_ops"] is True  # write_file in the raw content


def test_preview_intent_skill_detects_write_ops():
    """preview_intent correctly detects write operations from playbook content."""
    from kb_agent.skill.planner import preview_intent

    skill_no_write = _make_skill_def(raw="step 1: jira_fetch\nstep 2: summarize results")
    result_no_write = preview_intent("command", skill_def=skill_no_write)
    assert result_no_write["has_write_ops"] is False

    skill_with_write = _make_skill_def(raw="step 1: jira_fetch\nstep 2: write_file output.md")
    result_with_write = preview_intent("command", skill_def=skill_with_write)
    assert result_with_write["has_write_ops"] is True


# ─────────────────────────────────────────────────────────────────────────────
# preview_intent — free_agent path (LLM call)
# ─────────────────────────────────────────────────────────────────────────────

def test_preview_intent_free_agent_calls_llm():
    """preview_intent without skill_def makes one LLM call."""
    from kb_agent.skill.planner import preview_intent

    payload = {"summary": "I will fetch Jira tickets and save them.", "has_write_ops": True}
    llm = _make_llm(json.dumps(payload))

    result = preview_intent("fetch tickets and save", llm=llm)

    llm.invoke.assert_called_once()
    assert result["summary"] == payload["summary"]
    assert result["has_write_ops"] is True


def test_preview_intent_free_agent_llm_failure_fallback():
    """If LLM fails in preview_intent, returns command as summary."""
    from kb_agent.skill.planner import preview_intent

    llm = MagicMock()
    llm.invoke.side_effect = Exception("LLM error")

    result = preview_intent("my command", llm=llm)

    assert result["summary"] == "my command"
    assert result["has_write_ops"] is False


def test_preview_intent_no_llm_fallback():
    """preview_intent with no skill_def and no llm returns command as summary."""
    from kb_agent.skill.planner import preview_intent

    result = preview_intent("just a command")

    assert result["summary"] == "just a command"
    assert result["has_write_ops"] is False


# ─────────────────────────────────────────────────────────────────────────────
# _build_tool_history_str
# ─────────────────────────────────────────────────────────────────────────────




# ─────────────────────────────────────────────────────────────────────────────
# decide_next_step — prompt content verification
# ─────────────────────────────────────────────────────────────────────────────

def test_decide_prompt_contains_required_rules():
    """Verify that the DECIDE_NEXT_STEP_SYSTEM prompt contains the new rules and run_id."""
    from kb_agent.skill.planner import decide_next_step

    tool_calls = [{"name": "direct_response", "args": {"answer": "done"}, "id": "call_qwerty"}]
    llm = _make_llm(tool_calls=tool_calls)
    session = _make_session()
    session.run_id = "target-run-id"

    decide_next_step("calculate leap year", session, llm)

    llm.bind_tools.return_value.invoke.assert_called_once()
    call_args = llm.bind_tools.return_value.invoke.call_args[0][0]
    system_msg_content = call_args[0].content

    # Check for rules in system prompt (synced from PLANNER_SYSTEM)
    assert "python_code/' paths" in system_msg_content
    assert "target-run-id" in system_msg_content
