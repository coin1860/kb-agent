"""
Unit tests for skill/router.py
Tests: skill match, free_agent fallback, parse failure fallback.
"""

import json
from dataclasses import dataclass
from pathlib import Path
from unittest.mock import MagicMock

import pytest


@pytest.fixture
def skills():
    from kb_agent.skill.loader import SkillDef
    return {
        "weekly-jira-report": SkillDef(
            name="weekly-jira-report",
            description="Generate weekly Jira ticket summary report for the team",
            file_path=Path("weekly-jira-report.yaml"),
            raw_content="",
        ),
        "kb-search-and-save": SkillDef(
            name="kb-search-and-save",
            description="Search knowledge base and save results to a file",
            file_path=Path("kb-search-and-save.yaml"),
            raw_content="",
        ),
    }


def _make_llm(response_content: str):
    """Create a mock LLM that returns fixed content."""
    llm = MagicMock()
    msg = MagicMock()
    msg.content = response_content
    llm.invoke.return_value = msg
    return llm


def test_route_matches_skill(skills):
    from kb_agent.skill.router import route_intent

    llm = _make_llm(json.dumps({"route": "skill", "skill_id": "weekly-jira-report"}))
    result = route_intent("生成本周Jira周报", skills, llm)

    assert result.route == "skill"
    assert result.skill_id == "weekly-jira-report"


def test_route_free_agent(skills):
    from kb_agent.skill.router import route_intent

    llm = _make_llm(json.dumps({"route": "free_agent"}))
    result = route_intent("what is the weather today", skills, llm)

    assert result.route == "free_agent"
    assert result.skill_id is None


def test_route_nonexistent_skill_falls_back(skills):
    """If LLM returns a skill_id that doesn't exist in the index, fall back to free_agent."""
    from kb_agent.skill.router import route_intent

    llm = _make_llm(json.dumps({"route": "skill", "skill_id": "nonexistent-skill"}))
    result = route_intent("do something", skills, llm)

    assert result.route == "free_agent"


def test_route_parse_failure_fallback(skills):
    """If LLM returns garbage JSON, fall back gracefully to free_agent."""
    from kb_agent.skill.router import route_intent

    llm = _make_llm("This is not JSON at all!!!")
    result = route_intent("some command", skills, llm)

    assert result.route == "free_agent"


def test_route_no_skills():
    """With no skills loaded, always return free_agent without LLM call."""
    from kb_agent.skill.router import route_intent

    llm = MagicMock()
    result = route_intent("any command", {}, llm)

    assert result.route == "free_agent"
    llm.invoke.assert_not_called()
