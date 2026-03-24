"""
Skill loader — parses YAML playbooks from data_folder/skills/ and
expands Jinja2-style {{variable}} template tokens.
"""

from __future__ import annotations

import logging
import re
import warnings
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)


@dataclass
class SkillDef:
    """A loaded skill playbook."""
    name: str
    description: str
    file_path: Path
    raw_content: str
    # Steps are stored as plain dicts from YAML
    steps: list[dict] = field(default_factory=list)
    context_vars: dict = field(default_factory=dict)

    @property
    def short_description(self) -> str:
        """Return first 15 words for the routing prompt."""
        words = self.description.split()
        return " ".join(words[:15]) + ("..." if len(words) > 15 else "")


def _default_template_vars() -> dict:
    """Return default template variable values."""
    today = date.today()
    return {
        "date": today.isoformat(),
        "year": str(today.year),
        "month": str(today.month).zfill(2),
        "day": str(today.day).zfill(2),
    }


def _expand_template(text: str, extra_vars: dict | None = None) -> str:
    """Replace {{variable}} placeholders with resolved values."""
    vars_map = _default_template_vars()
    if extra_vars:
        vars_map.update(extra_vars)

    def replacer(match: re.Match) -> str:
        key = match.group(1).strip()
        return str(vars_map.get(key, match.group(0)))  # leave unresolved vars as-is

    return re.sub(r"\{\{(\w+)\}\}", replacer, text)


def _parse_skill_yaml(path: Path) -> Optional[SkillDef]:
    """Parse a single YAML skill file. Returns None on failure."""
    try:
        import yaml
    except ImportError:
        try:
            import pyyaml as yaml  # type: ignore[no-reattr]
        except ImportError:
            logger.error("PyYAML not installed — cannot load skills")
            return None

    try:
        with open(path, encoding="utf-8") as f:
            content = f.read()

        data = yaml.safe_load(content)
        if not isinstance(data, dict):
            warnings.warn(f"Skill '{path.name}' is not a YAML mapping — skipped", stacklevel=2)
            return None

        name = data.get("name") or path.stem
        description = str(data.get("description", ""))
        steps = data.get("steps", [])
        context_vars = data.get("context", {}) or {}

        if not isinstance(steps, list):
            steps = []

        return SkillDef(
            name=name,
            description=description,
            file_path=path,
            raw_content=content,
            steps=steps,
            context_vars=context_vars,
        )
    except Exception as e:
        warnings.warn(f"Failed to parse skill '{path.name}': {e} — skipped", stacklevel=2)
        return None


def load_skills(skills_path: Path) -> dict[str, SkillDef]:
    """
    Load all *.yaml skill files from skills_path.

    Returns a dict keyed by skill name. Malformed files are skipped with a warning.
    """
    skills: dict[str, SkillDef] = {}

    if not skills_path.exists():
        logger.info("Skills directory '%s' does not exist — no skills loaded", skills_path)
        return skills

    for yaml_file in sorted(skills_path.glob("*.yaml")):
        skill = _parse_skill_yaml(yaml_file)
        if skill is not None:
            skills[skill.name] = skill
            logger.debug("Loaded skill '%s' from %s", skill.name, yaml_file.name)

    return skills


def expand_skill_content(skill: SkillDef) -> str:
    """
    Return the skill's raw_content with template variables expanded.
    Uses context_vars from the skill definition plus default date vars.
    """
    return _expand_template(skill.raw_content, extra_vars=skill.context_vars)
