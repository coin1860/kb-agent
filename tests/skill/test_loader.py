"""
Unit tests for skill/loader.py
Tests: valid YAML loads, malformed YAML skipped, template expansion.
"""

import textwrap
import warnings
from pathlib import Path

import pytest


@pytest.fixture
def skills_dir(tmp_path):
    """Create a temporary skills directory."""
    d = tmp_path / "skills"
    d.mkdir()
    return d


def _write_skill(skills_dir: Path, filename: str, content: str) -> Path:
    p = skills_dir / filename
    p.write_text(content, encoding="utf-8")
    return p


def test_load_valid_skill(skills_dir):
    from kb_agent.skill.loader import load_skills

    _write_skill(skills_dir, "my-skill.yaml", textwrap.dedent("""\
        name: my-skill
        description: A test skill for unit testing
        steps:
          - id: step1
            description: Do something
    """))

    skills = load_skills(skills_dir)
    assert "my-skill" in skills
    skill = skills["my-skill"]
    assert skill.name == "my-skill"
    assert "test skill" in skill.description
    assert len(skill.steps) == 1


def test_load_malformed_skill_skipped(skills_dir):
    from kb_agent.skill.loader import load_skills

    _write_skill(skills_dir, "good.yaml", "name: good\ndescription: Good skill\n")
    _write_skill(skills_dir, "bad.yaml", ": invalid: yaml: [unclosed")

    with warnings.catch_warnings(record=True):
        warnings.simplefilter("always")
        skills = load_skills(skills_dir)

    assert "good" in skills
    assert "bad" not in skills


def test_load_empty_directory(tmp_path):
    from kb_agent.skill.loader import load_skills

    empty = tmp_path / "empty_skills"
    empty.mkdir()
    skills = load_skills(empty)
    assert skills == {}


def test_load_nonexistent_directory(tmp_path):
    from kb_agent.skill.loader import load_skills

    skills = load_skills(tmp_path / "nonexistent")
    assert skills == {}


def test_template_variable_expansion():
    import re
    from kb_agent.skill.loader import _expand_template

    result = _expand_template("Report for {{date}} in project {{project}}", extra_vars={"project": "FSR"})
    # date should be resolved
    assert "{{date}}" not in result
    assert "FSR" in result
    # date should be ISO format: YYYY-MM-DD
    assert re.search(r"\d{4}-\d{2}-\d{2}", result)


def test_template_unresolved_variable_preserved():
    from kb_agent.skill.loader import _expand_template

    result = _expand_template("Hello {{unknown_var}}")
    assert "{{unknown_var}}" in result


def test_short_description_truncated():
    from kb_agent.skill.loader import SkillDef
    from pathlib import Path

    skill = SkillDef(
        name="test",
        description="This is a very long description that has more than fifteen words in it so it should be truncated properly",
        file_path=Path("test.yaml"),
        raw_content="",
    )
    words = skill.short_description.split()
    # Should end with "..." and be max 15 real words + "..."
    assert skill.short_description.endswith("...")
    assert len(skill.description.split()) > 15
