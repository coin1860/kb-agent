"""Verification script for CLI skill enhancements."""
import sys
sys.path.insert(0, '/Users/shaneshou/Dev/kb-agent/src')

from pathlib import Path

print("=== Test 1: loader SKILL.md format ===")
from kb_agent.skill.loader import load_skills
skills = load_skills(Path('/Users/shaneshou/Dev/kb-agent/skills'))
print("Skills loaded:", list(skills.keys()))
pdf = skills.get('pdf')
if pdf:
    print("  skill_type:", pdf.skill_type)
    print("  sibling_docs:", [d.name for d in pdf.sibling_docs])
    print("  description[:80]:", pdf.description[:80])
    print("  raw_content[:60]:", pdf.raw_content[:60].replace('\n', ' '))
    print("  PASS")
else:
    print("  FAIL - pdf skill not found!")

print()
print("=== Test 2: shell_exec tool ===")
from kb_agent.tools.atomic.shell_exec import run_shell, _check_command_safety, ShellSecurityError
print("run_shell.name:", run_shell.name)
print("PASS")

print()
print("=== Test 3: run_shell in get_skill_tools ===")
from kb_agent.agent.tools import get_skill_tools
tool_names = [t.name for t in get_skill_tools()]
print("All tools:", tool_names)
print("run_shell present:", "run_shell" in tool_names)
print("PASS" if "run_shell" in tool_names else "FAIL")

print()
print("=== Test 4: APPROVAL_TOOLS ===")
from kb_agent.skill.planner import APPROVAL_TOOLS
print("APPROVAL_TOOLS:", APPROVAL_TOOLS)
print("run_shell in APPROVAL_TOOLS:", "run_shell" in APPROVAL_TOOLS)
print("PASS" if "run_shell" in APPROVAL_TOOLS else "FAIL")

print()
print("=== Test 5: safety guard ===")
try:
    _check_command_safety('rm -rf /tmp/test')
    print("FAIL - rm -rf should have been blocked")
except ShellSecurityError:
    print("PASS - rm -rf blocked")

try:
    _check_command_safety('qpdf --empty --pages f1.pdf f2.pdf -- out.pdf')
    print("PASS - qpdf allowed")
except ShellSecurityError as e:
    print("FAIL - qpdf blocked:", e)

print()
print("=== Test 6: _build_message_history has milestone_index param ===")
import inspect
from kb_agent.skill.planner import _build_message_history, decide_next_step
sig_bmh = inspect.signature(_build_message_history)
sig_dns = inspect.signature(decide_next_step)
has_bmh = 'milestone_index' in sig_bmh.parameters
has_dns = 'milestone_index' in sig_dns.parameters
print("_build_message_history has milestone_index:", has_bmh)
print("decide_next_step has milestone_index:", has_dns)
print("PASS" if (has_bmh and has_dns) else "FAIL")

print()
print("=== All done ===")
