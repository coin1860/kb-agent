"""
Unit and integration tests for the two-layer Milestone Planner architecture:
  - plan_milestones()
  - _parse_milestones()
  - _compress_milestone_result() (via SkillShell)
  - decide_next_step() with milestone_goal / prior_context params
  - _milestone_execute_loop() integration (2-milestone flow)
"""

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

def _make_llm(content: str):
    """Create a mock LLM that always returns fixed content."""
    llm = MagicMock()
    msg = MagicMock()
    msg.content = content
    msg.usage_metadata = {"output_tokens": 42}
    llm.invoke.return_value = msg
    return llm


def _make_session(run_id: str = "test-run-abc"):
    session = MagicMock()
    session.run_id = run_id
    return session


def _make_milestone(goal="Fetch data", expected="JSON response", budget=2):
    from kb_agent.skill.planner import Milestone
    return Milestone(goal=goal, expected_output=expected, iteration_budget=budget)


# ─────────────────────────────────────────────────────────────────────────────
# Task 7.1 — generate_unified_plan(): valid JSON response
# ─────────────────────────────────────────────────────────────────────────────

def test_unified_plan_valid_response():
    """generate_unified_plan() returns correct Plan from valid LLM JSON."""
    from kb_agent.skill.planner import generate_unified_plan

    plan_json = json.dumps({
        "route": "skill",
        "skill_id": "test_skill",
        "summary": "Fetching tickets",
        "has_write_ops": False,
        "milestones": [
            {"goal": "Fetch Jira tickets", "expected_output": "List of ticket summaries", "iteration_budget": 2},
            {"goal": "Write report to output/", "expected_output": "File at output/report.md", "iteration_budget": 3},
        ]
    })
    llm = _make_llm(plan_json)
    session = _make_session()

    result = generate_unified_plan("fetch Jira tickets and write report", session, {}, llm)

    assert result.route == "skill"
    assert result.skill_id == "test_skill"
    assert len(result.milestones) == 2
    assert result.milestones[0].goal == "Fetch Jira tickets"
    assert result.milestones[0].iteration_budget == 2
    assert result.milestones[1].goal == "Write report to output/"
    assert result.milestones[1].expected_output == "File at output/report.md"


def test_unified_plan_fenced_json():
    """generate_unified_plan() strips ```json code fences from LLM response."""
    from kb_agent.skill.planner import generate_unified_plan

    plan_json = json.dumps({
        "route": "free_agent",
        "summary": "say hello",
        "has_write_ops": False,
        "milestones": [
            {"goal": "Direct answer", "expected_output": "Answer text", "iteration_budget": 1}
        ]
    })
    fenced = f"```json\n{plan_json}\n```"
    llm = _make_llm(fenced)
    session = _make_session()

    result = generate_unified_plan("hello", session, {}, llm)

    assert result.route == "free_agent"
    assert len(result.milestones) == 1
    assert result.milestones[0].goal == "Direct answer"


def test_unified_plan_default_budget_applied():
    """Milestones missing iteration_budget get the default_budget value."""
    from kb_agent.skill.planner import generate_unified_plan

    plan_json = json.dumps({
        "route": "free_agent",
        "milestones": [
            {"goal": "Do something", "expected_output": "Result"}
            # No iteration_budget key
        ]
    })
    llm = _make_llm(plan_json)
    session = _make_session()

    result = generate_unified_plan("do something", session, {}, llm, default_budget=5)

    assert len(result.milestones) == 1
    assert result.milestones[0].iteration_budget == 5


# ─────────────────────────────────────────────────────────────────────────────
# Task 7.2 — generate_unified_plan(): fallback on invalid response
# ─────────────────────────────────────────────────────────────────────────────

def test_unified_plan_fallback_on_invalid_json():
    """generate_unified_plan() returns single fallback Milestone when LLM returns non-JSON."""
    from kb_agent.skill.planner import generate_unified_plan

    llm = _make_llm("This is not JSON at all.")
    session = _make_session()
    command = "do some complex thing"

    result = generate_unified_plan(command, session, {}, llm, default_budget=3)

    assert result.route == "free_agent"
    assert len(result.milestones) == 1
    assert result.milestones[0].goal == command
    assert result.milestones[0].expected_output == "Task completed"
    assert result.milestones[0].iteration_budget == 3


def test_unified_plan_fallback_on_empty_object():
    """generate_unified_plan() returns single fallback Milestone when LLM returns empty object."""
    from kb_agent.skill.planner import generate_unified_plan

    llm = _make_llm("{}")
    session = _make_session()
    command = "another task"

    result = generate_unified_plan(command, session, {}, llm)

    assert result.route == "free_agent"
    assert len(result.milestones) == 1
    assert result.milestones[0].goal == command


def test_unified_plan_fallback_on_llm_exception():
    """generate_unified_plan() returns single fallback Milestone when LLM raises."""
    from kb_agent.skill.planner import generate_unified_plan

    llm = MagicMock()
    llm.invoke.side_effect = RuntimeError("network error")
    session = _make_session()

    result = generate_unified_plan("something", session, {}, llm)

    assert result.route == "free_agent"
    assert len(result.milestones) == 1


# ─────────────────────────────────────────────────────────────────────────────
# Task 7.3 — _compress_milestone_result(): compression and fallback
# ─────────────────────────────────────────────────────────────────────────────

def test_compress_milestone_result_returns_summary():
    """_compress_milestone_result returns LLM summary on success."""
    from kb_agent.skill.shell import SkillShell

    milestone = _make_milestone()
    llm = _make_llm("The fetch returned 10 tickets from project PROJ.")

    # Instantiate _compress_milestone_result directly via an unbound call
    # by creating a minimal shell (mocked dependencies)
    shell = SkillShell.__new__(SkillShell)
    shell.renderer = MagicMock()
    shell.llm = llm

    result = shell._compress_milestone_result(milestone, "raw output here", llm)

    assert result == "The fetch returned 10 tickets from project PROJ."


def test_compress_milestone_result_fallback_on_exception():
    """_compress_milestone_result falls back to truncated raw_result when LLM raises."""
    from kb_agent.skill.shell import SkillShell

    milestone = _make_milestone()
    bad_llm = MagicMock()
    bad_llm.invoke.side_effect = RuntimeError("LLM down")

    shell = SkillShell.__new__(SkillShell)
    shell.renderer = MagicMock()
    shell.llm = bad_llm

    raw = "line1\nline2\nline3"
    result = shell._compress_milestone_result(milestone, raw, bad_llm)

    # Should return something from the raw result, not raise
    assert isinstance(result, str)
    assert len(result) > 0


# ─────────────────────────────────────────────────────────────────────────────
# Task 7.4 — decide_next_step() with milestone_goal param
# ─────────────────────────────────────────────────────────────────────────────

def test_decide_milestone_goal_appears_in_prompt():
    """When milestone_goal is passed, it appears in the LLM user message."""
    from kb_agent.skill.planner import decide_next_step

    payload = {"action": "final_answer", "answer": "done"}
    llm = _make_llm(json.dumps(payload))
    session = _make_session()

    decide_next_step(
        "fetch tickets and write report",
        session,
        llm,
        milestone_goal="Fetch Jira tickets for project PROJ",
    )

    llm.invoke.assert_called_once()
    call_args = llm.invoke.call_args[0][0]
    user_msg = call_args[1].content
    assert "Fetch Jira tickets for project PROJ" in user_msg
    assert "CURRENT MILESTONE GOAL" in user_msg


def test_decide_prior_context_appears_in_prompt():
    """When prior_context is passed, it appears in the LLM user message."""
    from kb_agent.skill.planner import decide_next_step

    payload = {"action": "final_answer", "answer": "done"}
    llm = _make_llm(json.dumps(payload))
    session = _make_session()

    decide_next_step(
        "multi-step task",
        session,
        llm,
        prior_context="Milestone 1 retrieved 5 tickets from PROJ.",
    )

    call_args = llm.invoke.call_args[0][0]
    user_msg = call_args[1].content
    assert "Milestone 1 retrieved 5 tickets from PROJ." in user_msg
    assert "Prior milestone context" in user_msg


def test_decide_no_milestone_goal_no_injection():
    """Without milestone_goal, no CURRENT MILESTONE GOAL section in prompt."""
    from kb_agent.skill.planner import decide_next_step

    payload = {"action": "final_answer", "answer": "done"}
    llm = _make_llm(json.dumps(payload))
    session = _make_session()

    decide_next_step("simple task", session, llm)

    call_args = llm.invoke.call_args[0][0]
    user_msg = call_args[1].content
    assert "CURRENT MILESTONE GOAL" not in user_msg
    assert "Prior milestone context" not in user_msg


# ─────────────────────────────────────────────────────────────────────────────
# Task 7.5 — _milestone_execute_loop() integration: 2-milestone flow
# ─────────────────────────────────────────────────────────────────────────────

def test_milestone_loop_two_milestones_second_gets_compressed_context(tmp_path):
    """
    Integration: _milestone_execute_loop() with 2 milestones.
    Asserts that:
    - _execute_milestone is called for each milestone
    - _compress_milestone_result is called after milestone 1
    - The compressed result is passed as prior_context to milestone 2
    """
    from kb_agent.skill.shell import SkillShell
    from kb_agent.skill.planner import Milestone
    from kb_agent.skill.interruptor import CancellationToken

    m1 = Milestone(goal="Fetch data", expected_output="JSON data", iteration_budget=1)
    m2 = Milestone(goal="Write report", expected_output="File at output/report.md", iteration_budget=1)

    # Build a minimal SkillShell
    shell = SkillShell.__new__(SkillShell)
    shell.renderer = MagicMock()
    shell.llm = MagicMock()
    shell._cli_max_iterations = 1
    shell._tool_map = {}
    shell.skills = {}

    # Track calls
    execute_calls: list[dict] = []
    compress_calls: list[str] = []

    def fake_execute_milestone(milestone, prior_context, session, cancel_token, command, skill_def, milestone_index):
        execute_calls.append({"goal": milestone.goal, "prior_context": prior_context})
        return f"result_of_{milestone_index}" * 1000  # Make it long enough (>8k chars) to trigger compression

    def fake_compress(milestone, raw_result, llm):
        compress_calls.append(raw_result)
        return f"compressed: {raw_result}"

    session = _make_session()
    cancel_token = CancellationToken()

    with patch("kb_agent.skill.shell.log_audit"), \
         patch.object(shell, "_execute_milestone", side_effect=fake_execute_milestone), \
         patch.object(shell, "_compress_milestone_result", side_effect=fake_compress):

        result = shell._milestone_execute_loop(
            command="fetch data and write report",
            milestones=[m1, m2],
            skill_def=None,
            session=session,
            cancel_token=cancel_token,
        )

    # Both milestones executed
    assert len(execute_calls) == 2
    assert execute_calls[0]["goal"] == "Fetch data"
    assert execute_calls[1]["goal"] == "Write report"

    # Compression was called once (after milestone 1, not milestone 2)
    assert len(compress_calls) == 1
    assert compress_calls[0] == "result_of_1" * 1000

    # Second milestone received the compressed first milestone context
    assert "compressed:" in execute_calls[1]["prior_context"]
    assert "result_of_1" in execute_calls[1]["prior_context"]

    # Final result is the last milestone's answer
    assert "result_of_2" in result
