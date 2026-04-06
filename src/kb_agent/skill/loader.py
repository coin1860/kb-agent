"""
Skill loader — parses YAML playbooks from data_folder/skills/ and
expands Jinja2-style {{variable}} template tokens.

Supports two skill formats:
  FORMAT A: skills/name.yaml           — YAML playbook (legacy)
  FORMAT B: skills/name/SKILL.md       — Markdown + YAML frontmatter (standard)
"""

from __future__ import annotations

import ast
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
    # Steps are stored as plain dicts from YAML (optional in SKILL.md frontmatter)
    steps: list[dict] = field(default_factory=list)
    context_vars: dict = field(default_factory=dict)
    # 'yaml' for .yaml files, 'markdown' for SKILL.md directory format
    skill_type: str = "yaml"
    # Sibling Markdown files in the skill directory (e.g. forms.md, reference.md)
    sibling_docs: list[Path] = field(default_factory=list)

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


def _extract_script_metadata(script_path: Path) -> str:
    """Extract docstring and usage info from a python script to provide to the LLM."""
    try:
        content = script_path.read_text(encoding="utf-8", errors="ignore")
    except Exception:
        return f"  - {script_path.name}"

    desc = ""
    try:
        mod = ast.parse(content)
        doc = ast.get_docstring(mod)
        if doc:
            desc = doc.strip().split("\n")[0]
    except Exception:
        pass

    usage = ""
    for line in content.splitlines():
        if "Usage:" in line:
            # Clean up print("Usage: ... ") wrapper
            usage = line.strip().strip("'\"").replace('print("', '').replace('")', '')
            break

    info = f"  - {script_path.name}\n"
    if usage:
        info += f"    {usage}\n"
    if desc:
        info += f"    Desc: {desc}\n"
    return info.rstrip()


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


def _parse_skill_md(path: Path) -> Optional[SkillDef]:
    """
    Parse a SKILL.md file (directory format).

    Expected format::
        ---
        name: pdf
        description: |
          Use this skill whenever ...
        steps:                         # optional semi-structured steps
          - name: Extract text
            tool: run_python
        ---
        # Full Markdown body ...

    Returns None on failure.
    """
    try:
        import yaml
    except ImportError:
        try:
            import pyyaml as yaml  # type: ignore[no-reattr]
        except ImportError:
            logger.error("PyYAML not installed — cannot load SKILL.md files")
            return None

    try:
        content = path.read_text(encoding="utf-8")

        # Parse YAML frontmatter between leading '---' delimiters
        frontmatter: dict = {}
        body = content
        if content.startswith("---"):
            parts = content.split("---", 2)
            if len(parts) >= 3:
                try:
                    frontmatter = yaml.safe_load(parts[1]) or {}
                except Exception as fm_err:
                    warnings.warn(
                        f"SKILL.md '{path}' — bad frontmatter: {fm_err}",
                        stacklevel=2,
                    )
                body = parts[2].strip()

        skill_dir = path.parent
        name = str(frontmatter.get("name") or skill_dir.name)
        description = str(frontmatter.get("description", "")).strip()
        steps_raw = frontmatter.get("steps", [])
        if not isinstance(steps_raw, list):
            steps_raw = []
        context_vars = frontmatter.get("context", {}) or {}

        # Collect sibling .md files (excluding SKILL.md itself)
        siblings = [
            p for p in sorted(skill_dir.glob("*.md"))
            if p.name.upper() != "SKILL.MD"
        ]

        # Scan for adjacent scripts directory and append to body
        scripts_dir = skill_dir / "scripts"
        if scripts_dir.is_dir():
            scripts = sorted(scripts_dir.glob("*.py"))
            if scripts:
                scripts_info = "\n\n=== AVAILABLE SCRIPTS ===\n"
                scripts_info += f"Location: {scripts_dir.absolute()}\n"
                scripts_info += "If one of these scripts EXACTLY fulfills the goal, use `run_shell` to execute it: `python <absolute_path> <args>`\n"
                scripts_info += "HOWEVER, if no script matches, you MUST use `write_file` and `run_python` to implement the logic described in the documentation above.\n\n"
                for script in scripts:
                    scripts_info += _extract_script_metadata(script) + "\n"
                body += scripts_info

        return SkillDef(
            name=name,
            description=description,
            file_path=path,
            raw_content=body,
            steps=steps_raw,
            context_vars=context_vars,
            skill_type="markdown",
            sibling_docs=siblings,
        )
    except Exception as e:
        warnings.warn(f"Failed to parse SKILL.md '{path}': {e} — skipped", stacklevel=2)
        return None


def load_skills(skills_path: Path) -> dict[str, SkillDef]:
    """
    Load all skills from skills_path.

    Supports two formats:
    - FORMAT A: ``skills/name.yaml``      — YAML playbook
    - FORMAT B: ``skills/name/SKILL.md``  — Markdown + YAML frontmatter directory

    Returns a dict keyed by skill name. Malformed files are skipped with a warning.
    FORMAT B takes precedence over FORMAT A for the same skill name.
    """
    skills: dict[str, SkillDef] = {}

    if not skills_path.exists():
        logger.info("Skills directory '%s' does not exist — no skills loaded", skills_path)
        return skills

    # Round 1: FORMAT A — *.yaml files (legacy)
    for yaml_file in sorted(skills_path.glob("*.yaml")):
        skill = _parse_skill_yaml(yaml_file)
        if skill is not None:
            skills[skill.name] = skill
            logger.debug("Loaded YAML skill '%s' from %s", skill.name, yaml_file.name)

    # Round 2: FORMAT B — subdirectory SKILL.md (standard directory format)
    for skill_dir in sorted(skills_path.iterdir()):
        if not skill_dir.is_dir():
            continue
        skill_md = skill_dir / "SKILL.md"
        if not skill_md.exists():
            # Also check lower-case variant
            skill_md = skill_dir / "skill.md"
            if not skill_md.exists():
                continue
        skill = _parse_skill_md(skill_md)
        if skill is not None:
            if skill.name in skills:
                logger.debug(
                    "SKILL.md '%s' overrides YAML skill '%s'",
                    skill_md, skill.name,
                )
            skills[skill.name] = skill
            logger.debug(
                "Loaded Markdown skill '%s' from %s",
                skill.name, skill_md.relative_to(skills_path),
            )

    return skills


def expand_skill_content(skill: SkillDef) -> str:
    """
    Return the skill's raw_content with template variables expanded.
    Uses context_vars from the skill definition plus default date vars.
    """
    return _expand_template(skill.raw_content, extra_vars=skill.context_vars)
