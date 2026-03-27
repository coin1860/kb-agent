"""
Unit tests for CLI smart routing (redesigned: RAG as tool, not path).

Tests:
  - free_agent queries route through generate_plan → execute (not RAG graph directly)
  - skill-matched queries still go through generate_plan → approve → execute
  - rag_query tool is available in get_skill_tools()
  - rag_query tool returns final_answer from compiled graph
"""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from kb_agent.skill.router import RouteResult


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

def _make_shell(skills=None, console=None):
    """Create a SkillShell with mocked dependencies (no real LLM or tools)."""
    from kb_agent.skill.shell import SkillShell

    llm = MagicMock()
    with patch("kb_agent.skill.shell.get_skill_tools", return_value=[]):
        shell = SkillShell(
            skills=skills or {},
            output_path=Path("/tmp/output"),
            python_code_path=Path("/tmp/python_code"),
            llm=llm,
            console=console or MagicMock(),
        )
    return shell


def _mock_session():
    """Return a minimal mock Session that satisfies SkillShell._run_command."""
    session = MagicMock()
    session.command = ""
    session.run_id = "test-run-id"
    return session


# ─────────────────────────────────────────────────────────────────────────────
# free_agent now calls generate_plan (not RAG graph directly)
# ─────────────────────────────────────────────────────────────────────────────

def test_free_agent_calls_generate_plan():
    """When route_intent returns free_agent, generate_plan should be called."""
    from kb_agent.skill.planner import PlanStep

    shell = _make_shell()
    shell._session = _mock_session()

    fake_plan = [
        PlanStep(step_number=1, description="answer hi", tool="vector_search",
                 args={"query": "hi"}, requires_approval=False)
    ]

    with patch("kb_agent.skill.shell.route_intent",
               return_value=RouteResult(route="free_agent")), \
         patch("kb_agent.skill.shell.generate_plan", return_value=fake_plan) as mock_plan, \
         patch.object(shell, "_approval_gate", return_value=fake_plan), \
         patch("kb_agent.skill.shell.SkillExecutor") as mock_exec_cls, \
         patch("kb_agent.skill.shell.CancellationToken"), \
         patch("kb_agent.skill.shell.InterruptHandler"), \
         patch("kb_agent.skill.shell.log_audit"), \
         patch.object(shell.renderer, "print_info"), \
         patch.object(shell.renderer, "print_result"):

        mock_exec = MagicMock()
        mock_exec.execute_plan.return_value = "hello back"
        mock_exec_cls.return_value = mock_exec
        shell._session.write_manifest = MagicMock()
        shell._session.cleanup = MagicMock()

        shell._run_command("hi")

    mock_plan.assert_called_once()
    # skill_def should be None for free_agent path
    call_kwargs = mock_plan.call_args
    assert call_kwargs[1].get("skill_def") is None or call_kwargs[0][3] is None


def test_free_agent_does_not_call_rag_graph_directly():
    """free_agent path must NOT call any RAG graph directly; it goes through execute_plan."""
    from kb_agent.skill.planner import PlanStep

    shell = _make_shell()
    shell._session = _mock_session()

    # SkillShell should not have _run_rag_query anymore
    assert not hasattr(shell, "_run_rag_query"), (
        "_run_rag_query should have been removed from SkillShell"
    )


def test_free_agent_generate_plan_no_skill_def():
    """free_agent generate_plan call must pass skill_def=None."""
    from kb_agent.skill.planner import PlanStep

    shell = _make_shell()
    shell._session = _mock_session()

    fake_plan = [
        PlanStep(step_number=1, description="run python", tool="run_python",
                 args={"script_path": "test.py"}, requires_approval=True)
    ]

    captured_skill_def = []

    def _capture_plan(command, session, llm, skill_def=None):
        captured_skill_def.append(skill_def)
        return fake_plan

    with patch("kb_agent.skill.shell.route_intent",
               return_value=RouteResult(route="free_agent")), \
         patch("kb_agent.skill.shell.generate_plan", side_effect=_capture_plan), \
         patch.object(shell, "_approval_gate", return_value=None), \
         patch.object(shell.renderer, "print_info"):

        shell._run_command("python 写一个程序计算3+3")

    assert captured_skill_def == [None], "free_agent must call generate_plan with skill_def=None"


# ─────────────────────────────────────────────────────────────────────────────
# skill path is unchanged
# ─────────────────────────────────────────────────────────────────────────────

def test_skill_path_calls_generate_plan_with_skill_def():
    """When route_intent matches a skill, generate_plan should be called with skill_def."""
    from kb_agent.skill.loader import SkillDef
    from kb_agent.skill.planner import PlanStep

    fake_skill = MagicMock(spec=SkillDef)
    fake_skill.name = "meeting-summary"
    shell = _make_shell(skills={"meeting-summary": fake_skill})
    shell._session = _mock_session()

    fake_plan = [
        PlanStep(step_number=1, description="search", tool="vector_search",
                 args={"query": "meeting"}, requires_approval=False)
    ]

    with patch("kb_agent.skill.shell.route_intent",
               return_value=RouteResult(route="skill", skill_id="meeting-summary")), \
         patch("kb_agent.skill.shell.generate_plan", return_value=fake_plan) as mock_plan, \
         patch.object(shell, "_approval_gate", return_value=fake_plan), \
         patch("kb_agent.skill.shell.SkillExecutor") as mock_exec_cls, \
         patch("kb_agent.skill.shell.CancellationToken"), \
         patch("kb_agent.skill.shell.InterruptHandler"), \
         patch("kb_agent.skill.shell.log_audit"), \
         patch.object(shell.renderer, "print_info"), \
         patch.object(shell.renderer, "print_result"):

        mock_exec = MagicMock()
        mock_exec.execute_plan.return_value = "skill result"
        mock_exec_cls.return_value = mock_exec
        shell._session.write_manifest = MagicMock()
        shell._session.cleanup = MagicMock()

        shell._run_command("summarize meeting")

    mock_plan.assert_called_once()
    # skill_def should be the matched skill
    call_args = mock_plan.call_args
    assert call_args[0][3] == fake_skill or call_args[1].get("skill_def") == fake_skill


def test_skill_path_approval_gate_called():
    """Skill path must call _approval_gate (free_agent also calls it now)."""
    from kb_agent.skill.loader import SkillDef
    from kb_agent.skill.planner import PlanStep

    fake_skill = MagicMock(spec=SkillDef)
    shell = _make_shell(skills={"my-skill": fake_skill})
    shell._session = _mock_session()

    fake_plan = [
        PlanStep(step_number=1, description="step", tool="vector_search",
                 args={"query": "x"}, requires_approval=False)
    ]

    with patch("kb_agent.skill.shell.route_intent",
               return_value=RouteResult(route="skill", skill_id="my-skill")), \
         patch("kb_agent.skill.shell.generate_plan", return_value=fake_plan), \
         patch.object(shell, "_approval_gate", return_value=None) as mock_gate, \
         patch.object(shell.renderer, "print_info"):

        shell._run_command("run skill")

    mock_gate.assert_called_once_with(fake_plan)


# ─────────────────────────────────────────────────────────────────────────────
# rag_query tool existence and behaviour
# ─────────────────────────────────────────────────────────────────────────────

def test_rag_query_tool_in_skill_tools():
    """rag_query must appear in the list returned by get_skill_tools()."""
    with patch("kb_agent.agent.tools._get_write_file") as mock_wf, \
         patch("kb_agent.agent.tools._get_run_python") as mock_rp:
        mock_wf.return_value = MagicMock(name="write_file")
        mock_rp.return_value = MagicMock(name="run_python")

        from kb_agent.agent.tools import get_skill_tools
        tools = get_skill_tools()
        tool_names = [t.name for t in tools]

    assert "rag_query" in tool_names, f"rag_query not found in skill tools: {tool_names}"


def test_rag_query_tool_returns_final_answer():
    """rag_query tool should invoke compile_graph and return final_answer."""
    from kb_agent.agent.tools import rag_query

    fake_graph = MagicMock()
    fake_graph.invoke.return_value = {"final_answer": "The answer is 42."}

    with patch("kb_agent.agent.graph.compile_graph", return_value=fake_graph):
        # rag_query is a LangChain @tool — call underlying func directly
        result = rag_query.invoke({"query": "what is 42?"})

    assert result == "The answer is 42."
    fake_graph.invoke.assert_called_once_with(
        {"query": "what is 42?", "messages": [], "status_callback": None}
    )


def test_rag_query_tool_handles_missing_final_answer():
    """If AgentState has no final_answer, rag_query returns empty string."""
    from kb_agent.agent.tools import rag_query

    fake_graph = MagicMock()
    fake_graph.invoke.return_value = {}

    with patch("kb_agent.agent.graph.compile_graph", return_value=fake_graph):
        result = rag_query.invoke({"query": "oops"})

    assert result == ""


def test_rag_query_no_status_callback():
    """rag_query must pass status_callback=None (silent, no progress emitted)."""
    from kb_agent.agent.tools import rag_query

    fake_graph = MagicMock()
    fake_graph.invoke.return_value = {"final_answer": "done"}

    with patch("kb_agent.agent.graph.compile_graph", return_value=fake_graph):
        rag_query.invoke({"query": "test"})

    state_passed = fake_graph.invoke.call_args[0][0]
    state_passed = fake_graph.invoke.call_args[0][0]
    assert state_passed["status_callback"] is None


# ─────────────────────────────────────────────────────────────────────────────
# direct_response tool and fallback
# ─────────────────────────────────────────────────────────────────────────────

def test_direct_response_tool_exists():
    """direct_response must appear in the list returned by get_skill_tools()."""
    with patch("kb_agent.agent.tools._get_write_file"), \
         patch("kb_agent.agent.tools._get_run_python"):
        from kb_agent.agent.tools import get_skill_tools
        tool_names = [t.name for t in get_skill_tools()]

    assert "direct_response" in tool_names


def test_direct_response_tool_returns_arg():
    """direct_response(answer='x') should return 'x'."""
    from kb_agent.agent.tools import direct_response
    assert direct_response.invoke({"answer": "hello"}) == "hello"


def test_planner_fallback_uses_direct_response():
    """If LLM fails, planner should fallback to direct_response (not vector_search)."""
    from kb_agent.skill.planner import generate_plan
    
    mock_llm = MagicMock()
    mock_llm.invoke.side_effect = Exception("LLM error")
    
    session = _mock_session()
    steps = generate_plan("hi", session, mock_llm)
    
    assert len(steps) == 1
    assert steps[0].tool == "direct_response"
    assert "Sorry" in steps[0].args["answer"]
