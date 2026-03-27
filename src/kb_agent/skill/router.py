"""
Intent router — classifies user commands as skill-matched or free-agent
using a single LLM call with compressed skill metadata.
"""

from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass
from typing import Optional

from langchain_core.messages import HumanMessage, SystemMessage

from kb_agent.audit import log_audit
from .loader import SkillDef

logger = logging.getLogger(__name__)

_MAX_DESC_WORDS = 15

ROUTER_SYSTEM = """\
You are an intent router for a CLI agent. You have a list of available skills.

Given the user's command, decide the best route.

Respond with ONLY valid JSON, no other text:
- If it is a greeting, chitchat, or a simple question you can answer with general knowledge (no tools needed): {"route": "chitchat"}
- If it matches a skill: {"route": "skill", "skill_id": "<skill name>"}
- If no skill matches but tools are needed: {"route": "free_agent"}

Rules:
- Use chitchat for: greetings (hi, hello, how are you), simple pleasantries, questions answerable without any external data or tools
- Match skill if the command's intent aligns with a skill's purpose, even if wording differs
- Prefer free_agent for generic queries, lookups, code tasks, or anything requiring external data not covered by a skill
- If uncertain between chitchat and free_agent, prefer free_agent
"""


@dataclass
class RouteResult:
    route: str          # "chitchat", "skill", or "free_agent"
    skill_id: Optional[str] = None


def _build_skill_index(skills: dict[str, SkillDef]) -> str:
    """Build a compact skill listing for the routing prompt."""
    if not skills:
        return "(no skills loaded)"
    lines = []
    for name, skill in skills.items():
        lines.append(f"- {name}: {skill.short_description}")
    return "\n".join(lines)


def route_intent(command: str, skills: dict[str, SkillDef], llm) -> RouteResult:
    """
    Classify a user command as skill-matched or free-agent.

    Args:
        command: The user's raw input string.
        skills: Dict of loaded skills (name → SkillDef).
        llm: A ChatOpenAI-compatible LLM instance.

    Returns:
        RouteResult with route='skill' (+ skill_id) or route='free_agent'.
    """
    if not skills:
        return RouteResult(route="free_agent")

    skill_index = _build_skill_index(skills)
    user_msg = f"Available skills:\n{skill_index}\n\nUser command: {command}"

    log_audit("skill_route_start", {"command": command[:200], "skill_count": len(skills)})

    try:
        response = llm.invoke([
            SystemMessage(content=ROUTER_SYSTEM),
            HumanMessage(content=user_msg),
        ])
        raw = response.content.strip()

        # Strip think tags
        raw = re.sub(r"<think>.*?</think>", "", raw, flags=re.DOTALL).strip()

        # Strip JSON code fences
        if "```" in raw:
            parts = raw.split("```")
            if len(parts) >= 3:
                raw = parts[1]
                if raw.startswith("json"):
                    raw = raw[4:]
                raw = raw.strip()

        parsed = json.loads(raw)
        route = parsed.get("route", "free_agent")
        skill_id = parsed.get("skill_id")

        # Validate skill_id exists
        if route == "skill" and skill_id and skill_id in skills:
            log_audit("skill_route_result", {"route": "skill", "skill_id": skill_id})
            return RouteResult(route="skill", skill_id=skill_id)
        elif route == "chitchat":
            log_audit("skill_route_result", {"route": "chitchat"})
            return RouteResult(route="chitchat")
        else:
            log_audit("skill_route_result", {"route": "free_agent"})
            return RouteResult(route="free_agent")

    except Exception as e:
        logger.warning("Router parse failed (%s) — defaulting to free_agent", e)
        log_audit("skill_route_fallback", {"error": str(e)})
        return RouteResult(route="free_agent")
