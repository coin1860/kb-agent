"""
Unit tests for the approval gate logic in SkillShell.
Tests: all-read plan auto-approves, plan-with-write requires approval.
"""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from kb_agent.skill.planner import PlanStep


def _make_shell(skills=None, console=None):
    """Create a SkillShell with mocked dependencies."""
    from kb_agent.skill.shell import SkillShell

    llm = MagicMock()
    output = MagicMock(spec=Path)
    output.__truediv__ = lambda self, x: MagicMock(spec=Path)
    python_code = MagicMock(spec=Path)
    python_code.__truediv__ = lambda self, x: MagicMock(spec=Path)

    with patch("kb_agent.skill.shell.get_skill_tools", return_value=[]):
        shell = SkillShell(
            skills=skills or {},
            output_path=Path("/tmp/output"),
            python_code_path=Path("/tmp/python_code"),
            llm=llm,
            console=console or MagicMock(),
        )
    return shell


def _read_only_plan():
    return [
        PlanStep(step_number=1, description="search", tool="vector_search",
                 args={"query": "test"}, requires_approval=False),
        PlanStep(step_number=2, description="fetch jira", tool="jira_fetch",
                 args={"issue_key": "PROJ-1"}, requires_approval=False),
    ]


def _plan_with_write():
    return [
        PlanStep(step_number=1, description="search", tool="vector_search",
                 args={"query": "test"}, requires_approval=False),
        PlanStep(step_number=2, description="write result", tool="write_file",
                 args={"path": "output/result.md", "content": "hi", "mode": "create"},
                 requires_approval=True),
    ]


def test_read_only_plan_auto_approves():
    """A plan with no approval-required steps should auto-approve."""
    shell = _make_shell()
    plan = _read_only_plan()

    # approval gate should return the plan directly without prompting
    with patch.object(shell.renderer, "print_plan_table"), \
         patch.object(shell.renderer, "print_info"), \
         patch.object(shell.renderer, "print_approval_prompt") as mock_prompt:

        result = shell._approval_gate(plan)

    # Should NOT have called the approval prompt
    mock_prompt.assert_not_called()
    assert result == plan


def test_plan_with_write_requires_approval():
    """A plan containing write_file requires explicit user approval."""
    shell = _make_shell()
    plan = _plan_with_write()

    with patch.object(shell.renderer, "print_plan_table"), \
         patch.object(shell.renderer, "print_approval_prompt", return_value="a") as mock_prompt:

        result = shell._approval_gate(plan)

    # Should have asked for approval
    mock_prompt.assert_called_once()
    assert result == plan


def test_plan_approval_quit_returns_none():
    """User choosing 'q' at approval gate returns None (cancel)."""
    shell = _make_shell()
    plan = _plan_with_write()

    with patch.object(shell.renderer, "print_plan_table"), \
         patch.object(shell.renderer, "print_approval_prompt", return_value="q"), \
         patch.object(shell.renderer, "print_info"):

        result = shell._approval_gate(plan)

    assert result is None


def test_plan_step_requires_approval_flag():
    """Verify that PlanStep.requires_approval correctly reflects tool type."""
    write_step = PlanStep(
        step_number=1, description="write file", tool="write_file",
        args={}, requires_approval=True
    )
    read_step = PlanStep(
        step_number=2, description="search", tool="vector_search",
        args={}, requires_approval=False
    )
    assert write_step.requires_approval is True
    assert read_step.requires_approval is False
