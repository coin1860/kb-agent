"""
Skill planner — generates and revises execution plans using the LLM.

Plans are lists of PlanStep objects, each specifying a tool call with
whether it requires user approval before execution.
"""

from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass, field
from typing import Optional

from langchain_core.messages import HumanMessage, SystemMessage

from kb_agent.audit import log_audit
from .loader import SkillDef, expand_skill_content
from .session import Session

logger = logging.getLogger(__name__)

APPROVAL_TOOLS = {"write_file", "run_python"}

SKILL_TOOLS_DESCRIPTION = """\
Available tools (with approval requirement):
1. vector_search(query: str) — Semantic search over ChromaDB knowledge base. [no approval]
   ⚠️  SUPPRESSED BY DEFAULT. Use ONLY when a user question cannot be answered directly
   AND requires semantic retrieval of documents. Do NOT use for greetings or simple chitchat.
2. read_file(file_path: str) — Read a local file by path. [no approval]
3. jira_fetch(issue_key: str) — Fetch a Jira ticket by key (e.g. PROJ-123). [no approval]
4. jira_jql(query: str) — Search Jira using natural language query. [no approval]
5. confluence_fetch(page_id: str) — Fetch a Confluence page by ID. [no approval]
6. confluence_create_page(parent_id: str, title: str, content: str) — Create a new Confluence page. [no approval]
7. web_fetch(url: str) — Fetch a web page and convert to Markdown. [no approval]
8. local_file_qa(filename_prefix: str) — Read a local file from datastore. [no approval]
9. csv_info(filename: str) — Get CSV schema and sample. [no approval]
10. csv_query(filename: str, query_json_str: str) — Query a CSV file. [no approval]
11. write_file(path: str, content: str, mode: str) — Write/delete a file under data_folder.
    mode: 'create' | 'overwrite' | 'append' | 'delete'. [REQUIRES APPROVAL]
12. run_python(script_path: str, timeout_seconds: int=60) — Execute a Python script. [REQUIRES APPROVAL]
13. rag_query(query: str) — Full RAG pipeline query over the knowledge base (semantic search + synthesis).
    [no approval] ⚠️  SUPPRESSED BY DEFAULT. ONLY use this tool when the user explicitly mentions RAG,
    e.g. "用RAG查", "RAG查询", "search knowledge base", "知识库搜索". Do NOT use for general questions,
    coding tasks, writing files, or anything that does not explicitly request RAG retrieval.
14. direct_response(answer: str) — Respond directly to the user with a message or chitchat.
    Use this for greetings, simple pleasantries, or questions you can answer without any external data.
"""

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
- requires_approval MUST be true for write_file and run_python, false for all others
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
        tools_section=SKILL_TOOLS_DESCRIPTION,
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
        tools_section=SKILL_TOOLS_DESCRIPTION,
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
