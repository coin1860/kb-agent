"""
Skill planner — generates and revises execution plans using the LLM.

Two-layer architecture:
- Milestone Planner (high-level): plan_milestones() decomposes a user command into an
  ordered list of coarse, verifiable Milestone objects in a single LLM call. The prompt
  intentionally omits tool names — it reasons about *goals*, not *how*.
- Step Executor (low-level): decide_next_step() selects one tool per iteration within a
  milestone sub-loop. When called with milestone_goal/prior_context it focuses on the
  current milestone only, keeping context bounded regardless of task length.

Legacy / compatibility:
- Static (legacy): generate_plan() produces a full ordered list of PlanStep objects.
- Dynamic (legacy flat): decide_next_step() without milestone params reproduces old flat loop.
- preview_intent() for upfront intent summary before execution.
"""

from __future__ import annotations

import json
import logging
import re
import ast
from dataclasses import dataclass, field
from typing import Any, Optional

from langchain_core.messages import HumanMessage, SystemMessage, BaseMessage, AIMessage, ToolMessage

from kb_agent.audit import log_audit
from .loader import SkillDef, expand_skill_content
from .session import Session

logger = logging.getLogger(__name__)

APPROVAL_TOOLS = {"write_file", "run_python", "confluence_create_page", "confluence_update_page"}

def _get_legacy_tools_description() -> str:
    from kb_agent.agent.tools import get_skill_tools
    tools = get_skill_tools()
    lines = ["Available tools (with approval requirement):"]
    for idx, t in enumerate(tools, 1):
        lines.append(f"{idx}. {t.name} - {getattr(t, 'description', '')}")
    return "\n".join(lines)

PLANNER_SYSTEM = """\
You are a task execution planner. Given a user command and optional skill playbook,
generate a concrete, numbered execution plan.

{tools_section}

OUTPUT: Return ONLY a JSON array of steps. Each step MUST have these exact fields:
[
  {{
    "step_number": 1,
    "description": "What this step does in plain language",
    "tool": "tool_name",
    "args": {{"arg1": "value1"}},
    "requires_approval": false
  }}
]

Rules:
- IF a skill playbook is provided, your execution plan SHOULD follow its logic, but you MUST NOT create separate steps for internal reasoning/summarization.
- Perform any required reasoning (like summarization or analysis) directly within the argument resolution of the tool call that needs it (e.g., generate the summary in the 'content' field of 'write_file').
- requires_approval MUST be true for write_file, run_python, and Confluence write tools, false for all others
- Keep steps atomic — focus on physical tool actions (write, fetch, create)
- Use the run_id '{run_id}' in 'python_code/' paths (e.g. 'python_code/{run_id}/step_1.py')
- For file outputs, use 'output/' prefix (e.g. 'output/report.md')
- For temporary intermediate files, use 'temp/' prefix (e.g. 'temp/data.json')
- If you need to execute Python code, you MUST FIRST use 'write_file' to save the script before using 'run_python' to execute it.
- Ensure all required files exist (via write_file or previous tool outputs) before they are used as arguments in subsequent tool calls.
- For greetings (hi, hello), simple pleasantries, or any question that does not require searching the knowledge base or local files, use the 'direct_response' tool.
- Do NOT use 'vector_search' or 'rag_query' unless the user intent clearly requires a knowledge base search.
- Do NOT include any text outside the JSON array
"""

REPLAN_SYSTEM = """\
You are a task execution planner. The user interrupted a running plan and wants to modify it.

Below is the remaining plan and the user's re-plan instruction.
Generate a revised execution plan for the remaining steps.

{tools_section}

OUTPUT: Return ONLY a JSON array of steps with the same schema as before.
"""


@dataclass
class PlanStep:
    step_number: int
    description: str
    tool: str
    args: dict = field(default_factory=dict)
    requires_approval: bool = False

    def to_dict(self) -> dict:
        return {
            "step_number": self.step_number,
            "description": self.description,
            "tool": self.tool,
            "args": self.args,
            "requires_approval": self.requires_approval,
        }


@dataclass
class Milestone:
    """
    A coarse, verifiable goal produced by the Milestone Planner.

    goal            — human-readable objective (what to achieve)
    expected_output — observable completion signal (what constitutes "done")
    iteration_budget — max tool calls allowed for this milestone's sub-loop
    """
    goal: str
    expected_output: str
    iteration_budget: int = 3


def _parse_plan(raw: str) -> list[PlanStep]:
    """Parse LLM response into a list of PlanStep objects."""
    # Strip think tags
    cleaned = re.sub(r"<think>.*?</think>", "", raw, flags=re.DOTALL).strip()

    # Strip code fences
    if "```" in cleaned:
        parts = cleaned.split("```")
        if len(parts) >= 3:
            fenced = parts[1]
            if fenced.startswith("json"):
                fenced = fenced[4:]
            cleaned = fenced.strip()

    # Find JSON array
    start = cleaned.find("[")
    if start != -1:
        depth = 0
        for i in range(start, len(cleaned)):
            if cleaned[i] == "[":
                depth += 1
            elif cleaned[i] == "]":
                depth -= 1
            if depth == 0:
                try:
                    data = json.loads(cleaned[start:i + 1])
                    break
                except json.JSONDecodeError:
                    break
        else:
            data = []
    else:
        data = []

    steps = []
    for item in data:
        if not isinstance(item, dict) or "tool" not in item:
            continue
        tool_name = item.get("tool", "")
        # Auto-set requires_approval based on tool name if not specified
        requires_approval = item.get("requires_approval", tool_name in APPROVAL_TOOLS)
        steps.append(PlanStep(
            step_number=item.get("step_number", len(steps) + 1),
            description=item.get("description", ""),
            tool=tool_name,
            args=item.get("args", {}),
            requires_approval=requires_approval,
        ))
    return steps


def generate_plan(
    command: str,
    session: Session,
    llm,
    skill_def: Optional[SkillDef] = None,
) -> list[PlanStep]:
    """
    Generate an execution plan for the user command.

    Args:
        command: The user's raw command.
        session: Active session (provides run_id for path construction).
        llm: ChatOpenAI-compatible LLM.
        skill_def: Optional matched skill playbook.

    Returns:
        List of PlanStep objects in execution order.
    """
    system_prompt = PLANNER_SYSTEM.format(
        tools_section=_get_legacy_tools_description(),
        run_id=session.run_id,
    )

    user_parts = [f"User command: {command}"]
    if skill_def:
        expanded = expand_skill_content(skill_def)
        user_parts.append(f"\nSkill playbook '{skill_def.name}':\n{expanded}")

    user_msg = "\n".join(user_parts)

    log_audit("skill_plan_start", {"command": command[:200], "skill": skill_def.name if skill_def else None})

    try:
        response = llm.invoke([
            SystemMessage(content=system_prompt),
            HumanMessage(content=user_msg),
        ])
        raw = response.content.strip()
        steps = _parse_plan(raw)

        if not steps:
            logger.warning("Planner returned empty plan, using fallback")
            steps = [PlanStep(
                step_number=1,
                description=f"Direct Response: {command}",
                tool="direct_response",
                args={"answer": f"I understood your request: {command}"},
                requires_approval=False,
            )]

        log_audit("skill_plan_result", {"steps": [s.tool for s in steps]})
        return steps

    except Exception as e:
        logger.error("Planner failed: %s", e)
        return [PlanStep(
            step_number=1,
            description=f"Error fallback: {command}",
            tool="direct_response",
            args={"answer": f"Sorry, I encountered an error planning your request: {command}"},
            requires_approval=False,
        )]


def replan(
    remaining_steps: list[PlanStep],
    edit_instruction: str,
    session: Session,
    llm,
) -> list[PlanStep]:
    """
    Revise the remaining plan based on a user's re-plan instruction.

    Args:
        remaining_steps: Steps not yet executed.
        edit_instruction: User's natural language modification instruction.
        session: Active session.
        llm: ChatOpenAI-compatible LLM.

    Returns:
        Revised list of PlanStep objects.
    """
    system_prompt = REPLAN_SYSTEM.format(
        tools_section=_get_legacy_tools_description(),
    )

    remaining_json = json.dumps([s.to_dict() for s in remaining_steps], ensure_ascii=False, indent=2)
    user_msg = (
        f"Remaining plan:\n{remaining_json}\n\n"
        f"User's re-plan instruction: {edit_instruction}\n\n"
        f"Run ID for paths: {session.run_id}"
    )

    log_audit("skill_replan_start", {"instruction": edit_instruction[:200]})

    try:
        response = llm.invoke([
            SystemMessage(content=system_prompt),
            HumanMessage(content=user_msg),
        ])
        steps = _parse_plan(response.content.strip())
        if steps:
            return steps
    except Exception as e:
        logger.error("Replan failed: %s", e)

    return remaining_steps  # Fall back to existing plan on failure


# ─────────────────────────────────────────────────────────────────────────────
# Milestone Planner — high-level goal decomposition
# ─────────────────────────────────────────────────────────────────────────────

UNIFIED_PLANNER_SYSTEM = """\
You are a task analysis and planning agent. Given a user command and a list of available skills, perform routing, intent preview, and milestone planning in a single step.

Available skills:
{skill_index}

Task Types (Routes):
- chitchat: Greetings, pleasantries, or simple questions answerable without tools.
- skill: The command's intent matches one of the available skills.
- free_agent: The command requires tools/actions but does not match any specific skill.

Intent Preview:
Provide a brief summary of what you plan to do. 
- **CRITICAL**: If the route is 'chitchat', the 'summary' MUST be the actual final natural-language response to the user (e.g., "Hello! How can I help you today?").
- For other routes, provide a 1-2 sentence summary of the plan.
- Determine if the task requires sensitive write operations (writing files or running code).

Milestone Planning (only if route is 'skill' or 'free_agent'):
Decompose the task into an ordered list of 1-5 coarse, verifiable milestones before any tools are called. Each milestone describes a GOAL and an EXPECTED OUTPUT.
- Each milestone MUST capture a distinct phase of environmental interaction (fetching, querying, writing, executing).
- If the user specifies a specific technical method (e.g., "use Python", "run a script", "search Jira"), the milestone GOAL MUST explicitly include that requirement (e.g. "Execute Python code to...") to prevent the executor from skipping it.
- Do NOT list individual tool calls, but DO capture the major technical actions requested by the user.
- 1-2 milestones for fetch + write workflows
- Up to 5 for complex multi-phase tasks
- iteration_budget: 1 for simple read-only lookups.
- iteration_budget: 2-3 for simple write/execute tasks.
- iteration_budget: 4-6 for complex analysis, multi-file edits, or tasks with potential retries.

OUTPUT: Return ONLY a JSON object with this exact schema:
{{
  "route": "chitchat" | "skill" | "free_agent",
  "skill_id": "<skill name or null>",
  "summary": "<the actual response for chitchat, OR a 1-2 sentence intent summary for others>",
  "has_write_ops": <true or false>,
  "milestones": [
    {{
      "goal": "<objective>",
      "expected_output": "<completion signal>",
      "iteration_budget": <int, 1-6>
    }}
  ]
}}
"""



def _parse_milestones(raw: str, default_budget: int = 3) -> list[Milestone]:
    """Parse LLM response into a list of Milestone objects.

    Mirrors the _parse_plan() pattern: strips think tags, code fences, then
    extracts the first JSON array.
    """
    # Strip think tags
    cleaned = re.sub(r"<think>.*?</think>", "", raw, flags=re.DOTALL).strip()

    # Strip code fences
    if "```" in cleaned:
        parts = cleaned.split("```")
        if len(parts) >= 3:
            fenced = parts[1]
            if fenced.startswith("json"):
                fenced = fenced[4:]
            cleaned = fenced.strip()

    # Find JSON array
    start = cleaned.find("[")
    data: list = []
    if start != -1:
        depth = 0
        for i in range(start, len(cleaned)):
            if cleaned[i] == "[":
                depth += 1
            elif cleaned[i] == "]":
                depth -= 1
            if depth == 0:
                try:
                    data = json.loads(cleaned[start:i + 1])
                except json.JSONDecodeError:
                    pass
                break

    milestones = []
    for item in data:
        if not isinstance(item, dict) or "goal" not in item:
            continue
        milestones.append(Milestone(
            goal=item.get("goal", ""),
            expected_output=item.get("expected_output", ""),
            iteration_budget=int(item.get("iteration_budget", default_budget)),
        ))
    return milestones


@dataclass
class UnifiedPlanResponse:
    route: str
    skill_id: Optional[str]
    summary: str
    has_write_ops: bool
    milestones: list[Milestone]

def generate_unified_plan(
    command: str,
    session: Session,
    skills: dict[str, SkillDef],
    llm,
    default_budget: int = 3,
) -> UnifiedPlanResponse:
    """
    Unified function addressing: Intent routing, Intent preview, and Milestone Planning.
    """
    from .router import _build_skill_index
    skill_index = _build_skill_index(skills)
    
    system_prompt = UNIFIED_PLANNER_SYSTEM.format(skill_index=skill_index)
    user_msg = f"User command: {command}"

    log_audit("unified_plan_start", {"command": command[:200]})

    fallback = UnifiedPlanResponse(
        route="free_agent",
        skill_id=None,
        summary=command,
        has_write_ops=False,
        milestones=[Milestone(goal=command, expected_output="Task completed", iteration_budget=default_budget)]
    )

    try:
        response = llm.invoke([
            SystemMessage(content=system_prompt),
            HumanMessage(content=user_msg),
        ])
        raw = response.content.strip()
        
        # Strip think tags
        cleaned = re.sub(r"<think>.*?</think>", "", raw, flags=re.DOTALL).strip()
        if "```" in cleaned:
            parts = cleaned.split("```")
            if len(parts) >= 3:
                fenced = parts[1]
                if fenced.startswith("json"):
                    fenced = fenced[4:]
                cleaned = fenced.strip()

        # Find JSON object
        start = cleaned.find("{")
        if start != -1:
            depth = 0
            for i in range(start, len(cleaned)):
                if cleaned[i] == "{":
                    depth += 1
                elif cleaned[i] == "}":
                    depth -= 1
                if depth == 0:
                    data = json.loads(cleaned[start:i + 1])
                    break
            else:
                data = {}
        else:
            data = {}

        if not isinstance(data, dict):
            return fallback

        route = data.get("route", "free_agent")
        skill_id = data.get("skill_id")
        summary = data.get("summary", command)
        has_write_ops = data.get("has_write_ops", False)
        
        milestones = []
        for ms in data.get("milestones", []):
            if isinstance(ms, dict) and "goal" in ms:
                milestones.append(Milestone(
                    goal=ms.get("goal", ""),
                    expected_output=ms.get("expected_output", ""),
                    iteration_budget=int(ms.get("iteration_budget", default_budget)),
                ))
        
        if not milestones and route != "chitchat":
            milestones = fallback.milestones

        return UnifiedPlanResponse(
            route=route,
            skill_id=skill_id,
            summary=summary,
            has_write_ops=has_write_ops,
            milestones=milestones
        )

    except Exception as e:
        logger.error("unified_plan failed: %s", e)
        return fallback


# ─────────────────────────────────────────────────────────────────────────────
# Dynamic decision loop helpers
# ─────────────────────────────────────────────────────────────────────────────

DECIDE_NEXT_STEP_SYSTEM = """\
You are a step-by-step task executor. Decide ONE action at a time.

You are given:
- The user's original command
- (Optional) The CURRENT MILESTONE GOAL — your sole focus for this sub-loop
- (Optional) Prior milestone context — compressed summaries of already-completed milestones
- Optional skill playbook steps (HARD CONSTRAINTS — follow them in order, do not skip)
- History of tool calls already executed (with their results)
- Current iteration number and maximum allowed iterations

{tools_section}

Rules:
- If a CURRENT MILESTONE GOAL is provided, focus ONLY on achieving that goal — do not
  attempt work belonging to other milestones
- ALWAYS output final_answer if the CURRENT MILESTONE GOAL is fully achieved (e.g., you have successfully called the necessary tools and observed the results).
- You MUST call tools to interact with the environment (e.g., read, search, write files, execute code). Do NOT hallucinate task completion.
- For action-oriented goals (writing, running code, etc.), the milestone is NEVER achieved until the corresponding tool has been successfully executed. Even if you "know" the answer, you must perform the physical action requested (e.g., if asked to use Python to calculate 2x2, you MUST write and run Python, not just answer 4).
- When using semantic search tools (vector_search, rag_query, jira_jql), ALWAYS use descriptive natural language queries (e.g., "Find information about Shane's roles and projects") instead of single keywords (e.g., "Shane").
- If a skill playbook is provided, you MUST execute its steps in order without skipping
- Do NOT call the same tool with identical args twice (check history)
- If iteration >= max_iterations, you MUST use the direct_response or final answer tool immediately (even partial)
- Use the run_id '{run_id}' in 'python_code/' paths (e.g. 'python_code/{run_id}/step_1.py')
- For file outputs, use 'output/' prefix (e.g. 'output/report.md')
- For temporary intermediate files, use 'temp/' prefix (e.g. 'temp/data.json')
- If you need to execute Python code, you MUST FIRST use 'write_file' to save the script before using 'run_python' to execute it.
- Ensure all required files exist (via write_file or previous tool outputs) before they are used as arguments in subsequent tool calls.

**CRITICAL TOOL CALLING FORMAT**:
- You MUST use the native tool calling mechanism.
- Do NOT wrap your output in <function> or any other XML tags.
- Output ONLY the tool call.
- Use JSON-compatible types (e.g., true/false for booleans, not strings "true"/"false").

**CRITICAL: You must output tool calls in PURE JSON format. NEVER use tags like <function> or markdown code blocks. The response must be a valid JSON object or list and nothing else.**

OUTPUT: Return a tool call. If the task is fully achieved and you want to reply to the user directly, please invoke the `direct_response` tool.
"""

PREVIEW_INTENT_SYSTEM = """\
You are a task preview assistant. Given a user command, generate a brief summary
of what you plan to do, and whether any SENSITIVE write operations will be needed.

SENSITIVE operations requiring approval are:
- writing/deleting files (write_file tool)
- executing python scripts (run_python tool)

Non-sensitive operations:
- any read-only lookup or search
- providing a direct natural-language response/summary to the user

OUTPUT: Return ONLY valid JSON:
{"summary": "<1-2 sentence human-readable plan summary>", "has_write_ops": <true|false>}

Do NOT include any text outside the JSON.
"""


def _truncate_messages(messages: list[BaseMessage], max_messages: int = 20) -> list[BaseMessage]:
    """Keep system prompt and the N latest messages, ensuring AIMessage-ToolMessage pairs stay together."""
    if len(messages) <= max_messages:
        return messages
    
    # We always keep the first message (SystemMessage)
    system_msg = messages[0]
    others = messages[1:]
    
    # Take the last N-1 messages
    truncated = others[-(max_messages-1):]
    
    # If the first message in our truncation is a ToolMessage, it means we cut off its AIMessage.
    # To keep the history valid, we drop that orphaned ToolMessage.
    if truncated and isinstance(truncated[0], ToolMessage):
        truncated = truncated[1:]
        
    return [system_msg] + truncated

def _build_message_history(
    command: str,
    tool_history: list[dict[str, Any]],
    milestone_goal: Optional[str] = None,
    prior_context: Optional[str] = None,
    skill_def: Optional[SkillDef] = None,
    session_run_id: str = "",
    iteration: int = 1,
    max_iterations: int = 3,
) -> list[BaseMessage]:
    """Build LangChain message history from the task state for bind_tools."""
    sys_parts = [DECIDE_NEXT_STEP_SYSTEM.format(
        run_id=session_run_id,
        tools_section=_get_legacy_tools_description()
    )]
    system_msg = SystemMessage(content="\n".join(sys_parts))
    
    user_parts = [f"User command: {command}"]
    if milestone_goal:
        user_parts.append(f"\n🎯 CURRENT MILESTONE GOAL (focus ONLY on this):\n{milestone_goal}")
    if prior_context:
        user_parts.append(f"\n📋 Prior milestone context:\n{prior_context}")
    if skill_def:
        expanded = expand_skill_content(skill_def)
        user_parts.append(f"\n⚠️  SKILL PLAYBOOK HARD CONSTRAINT:\n'{skill_def.name}':\n{expanded}")
    
    messages: list[BaseMessage] = [system_msg, HumanMessage(content="\n".join(user_parts))]
    
    for entry in tool_history:
        tool_name = entry.get("tool", "")
        args = entry.get("args", {})
        result = str(entry.get("result", ""))
        status = entry.get("status", "")
        call_id = entry.get("tool_call_id", f"call_{entry.get('step', '0')}")
        
        if status == "skipped":
            result = "[user skipped]"
            
        ai_msg = AIMessage(
            content="", 
            tool_calls=[{"name": tool_name, "args": args, "id": call_id}]
        )
        tool_msg = ToolMessage(content=result, name=tool_name, tool_call_id=call_id)
        messages.extend([ai_msg, tool_msg])
        
    iter_prompt = f"\n\nIteration: {iteration} / {max_iterations}"
    if iteration >= max_iterations:
        iter_prompt += "\n🚨 MAX ITERATIONS REACHED. You MUST query `direct_response` to output the final answer now."
    
    # Instead of appending a new HumanMessage (which causes consecutive user messages and HTTP 400),
    # we append the iteration info to the last HumanMessage in the list.
    for i in range(len(messages) - 1, -1, -1):
        if isinstance(messages[i], HumanMessage):
            messages[i].content = str(messages[i].content) + iter_prompt
            break
    else:
        # Fallback if no HumanMessage found (shouldn't happen with our construction)
        messages.append(HumanMessage(content=iter_prompt))
    
    return _truncate_messages(messages)

def decide_next_step(
    command: str,
    session: Session,
    llm,
    skill_def: Optional[SkillDef] = None,
    tool_history: Optional[list[dict[str, Any]]] = None,
    iteration: int = 1,
    max_iterations: int = 3,
    milestone_goal: Optional[str] = None,
    prior_context: Optional[str] = None,
) -> dict[str, Any]:
    """
    Ask the LLM to decide the single next action natively using bind_tools().
    """
    from kb_agent.agent.tools import get_skill_tools
    
    tool_history = tool_history or []
    
    messages = _build_message_history(
        command=command,
        tool_history=tool_history,
        milestone_goal=milestone_goal,
        prior_context=prior_context,
        skill_def=skill_def,
        session_run_id=session.run_id,
        iteration=iteration,
        max_iterations=max_iterations,
    )

    log_audit("skill_decide_start", {
        "command": command[:200],
        "iteration": iteration,
        "history_len": len(tool_history),
    })

    try:
        tools = get_skill_tools()
        llm_with_tools = llm.bind_tools(tools)
        response = llm_with_tools.invoke(messages)
        
        # 1. Native tool_calls (standard path)
        if hasattr(response, "tool_calls") and response.tool_calls:
            tc = response.tool_calls[0]
            return _format_tool_response(tc, response.content)
            
        # 2. Text-based tool calls (fallback for llama3/etc. that bypass the validator)
        content = str(response.content or "")
        tool_pattern = r"<function=(\w+)(.*?)>(</function>|$)"
        match = re.search(tool_pattern, content, re.DOTALL)
        if match:
            tool_name = match.group(1)
            args_raw = match.group(2).strip()
            args = _parse_args_safely(args_raw)
            logger.info("Extracted tool call from response content: %s", tool_name)
            return _format_tool_response({"name": tool_name, "args": args, "id": f"text_{iteration}"}, content)
            
        # 3. Final answer (no tool calls)
        log_audit("skill_decide_result", {"action": "final_answer", "tool": "none"})
        return {
            "action": "final_answer",
            "answer": response.content
        }
            
    except Exception as e:
        logger.error("decide_next_step failed (iter %d): %s", iteration, e)
        
        # 4. Global robust fallback for errors (e.g. 400 error with XML tags in failed_generation)
        # We search the ENTIRE error message for <function=... tags.
        error_msg = str(e)
        match = re.search(r"<function=(\w+)(.*?)>(</function>|$|\n)", error_msg, re.DOTALL)
        if match:
            tool_name = match.group(1)
            args = _parse_args_safely(match.group(2).strip())
            logger.info("Successfully extracted tool call from error message: %s", tool_name)
            return _format_tool_response({"name": tool_name, "args": args, "id": f"err_fallback_{iteration}"}, error_msg)

        return {
            "action": "final_answer",
            "answer": f"Sorry, I encountered an error while planning your request: {command}",
        }

def _parse_args_safely(raw: str) -> dict:
    """Best-effort JSON argument parsing for messy LLM outputs."""
    if not raw:
        return {}
    try:
        # 1. Direct JSON
        return json.loads(raw)
    except:
        # 2. Extract first {...} blob
        json_match = re.search(r"({.*})", raw, re.DOTALL)
        if json_match:
            try:
                return json.loads(json_match.group(1))
            except:
                pass
        return {}

def _format_tool_response(tc: dict | Any, raw_content: str) -> dict:
    """Consistency wrapper for tool call responses."""
    if isinstance(tc, dict):
        name = tc.get("name", "")
        args = tc.get("args", {})
        call_id = tc.get("id", "unknown")
    else:
        name = tc.name
        args = tc.args
        call_id = tc.id

    if name == "direct_response":
        log_audit("skill_decide_result", {"action": "final_answer", "tool": "direct_response"})
        return {
            "action": "final_answer",
            "answer": args.get("answer", raw_content),
            "tool_call_id": call_id
        }
    else:
        log_audit("skill_decide_result", {"action": "call_tool", "tool": name})
        return {
            "action": "call_tool",
            "tool": name,
            "args": args,
            "reason": raw_content or f"Calling {name}",
            "tool_call_id": call_id,
            "finish_milestone": False
        }


def preview_intent(
    command: str,
    skill_def: Optional[SkillDef] = None,
    llm=None,
) -> dict[str, Any]:
    """
    Generate a brief intent summary for upfront user approval.

    - If skill_def is provided: derive summary from playbook steps (no LLM call).
    - Otherwise: make a lightweight LLM call to produce the summary.

    Returns: {"summary": str, "has_write_ops": bool}
    """
    if skill_def:
        # Derive from playbook without calling LLM
        expanded = expand_skill_content(skill_def)
        # Extract step titles if available, else summarise
        lines = [line.strip() for line in expanded.splitlines() if line.strip()]
        step_lines: list[str] = [l for l in lines if l.startswith(("step", "Step", "-", "*", "1.", "2.", "3."))]
        summary_body = "\n".join(step_lines[:6]) if step_lines else expanded[:300]
        has_write_ops = any(
            tool in expanded for tool in APPROVAL_TOOLS
        )
        return {
            "summary": f"Running skill '{skill_def.name}':\n{summary_body}",
            "has_write_ops": has_write_ops,
        }

    # Free-agent path: lightweight LLM call
    if llm is None:
        return {"summary": command, "has_write_ops": False}

    try:
        response = llm.invoke([
            SystemMessage(content=PREVIEW_INTENT_SYSTEM),
            HumanMessage(content=f"User command: {command}"),
        ])
        raw = response.content.strip()
        raw = re.sub(r"<think>.*?</think>", "", raw, flags=re.DOTALL).strip()
        if "```" in raw:
            parts_list = raw.split("```")
            if len(parts_list) >= 3:
                fenced = parts_list[1]
                if fenced.startswith("json"):
                    fenced = fenced[4:]
                raw = fenced.strip()
        result = json.loads(raw)
        if isinstance(result, dict) and "summary" in result:
            return result
    except Exception as e:
        logger.warning("preview_intent LLM call failed: %s", e)

    # Fallback: use command as summary
    return {"summary": command, "has_write_ops": False}
