"""
Skill executor — runs plan steps with Think/Act/Observe/Reflect,
cancellation-token-based interrupt support, and step audit trail.

Primary usage (as of hierarchical-planner-executor change):
  _execute_step() is called by SkillShell._execute_milestone() for each tool
  call within a milestone sub-loop, providing Reflect + retry + Python auto-fix
  in the main execution path (not only in the legacy static-plan path).

Legacy usage:
  execute_plan() accepts a pre-built list[PlanStep] and runs them sequentially.
  Still valid for skill-playbook-driven flows and direct testing.
"""

from __future__ import annotations

import json
import logging
import re
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from langchain_core.messages import HumanMessage, SystemMessage

from kb_agent.audit import log_audit
from .interruptor import CancellationToken
from .planner import PlanStep, replan
from .renderer import SkillRenderer
from .session import Session, StepRecord

logger = logging.getLogger(__name__)

_MAX_RETRIES = 2
_AUTO_FIX_MAX = 3

SAFE_READ_TOOLS = {
    "jira_fetch", "jira_jql", "vector_search", "get_knowledge", 
    "ls", "list_dir", "grep", "grep_search", "view_file", 
    "read_url_content", "read_browser_page", "command_status", 
    "direct_response"
}

REFLECT_SYSTEM = """\
You are evaluating whether a tool execution step succeeded and the plan should continue.

Given the step description, tool used, arguments, and the result, decide:
- "continue": step completed successfully, move to next step
- "retry": step failed or result is clearly wrong, should retry
- "abort": unrecoverable error, stop execution

Respond with ONLY valid JSON: {"verdict": "continue"|"retry"|"abort", "reason": "<brief reason>"}
"""

AUTO_FIX_SYSTEM = """\
You are a Python error auto-repair assistant.

A Python script failed to run. Given the script path, its content, and the error output,
decide the best repair action:

- "pip_install": a required package is missing (ModuleNotFoundError / ImportError)
  → Output JSON: {"action": "pip_install", "package": "name_of_package"}
- "patch_code": target a specific block of buggy code and replace it (Surgical Patch)
  → Output JSON: {"action": "patch_code", "search_block": "exact lines to find", "replace_block": "lines to replace them with"}
- "give_up": the error is unrecoverable or unclear
  → Output JSON: {"action": "give_up"}

CRITICAL RULES for patch_code:
- `search_block` MUST be a *perfect* character-for-character substring of the original file, including all exact leading spaces/indentation!
- Provide 2-3 lines of unchanged code above and below your fix within the `search_block` serving as ANCHORS to ensure uniqueness.
- Only change the MINIMUM number of lines needed to fix the specific error.
- DO NOT rewrite the entire file unless the whole file genuinely needs rewriting.
- DO NOT output the `search_block` or `replace_block` in markdown fences outside the JSON. All patch data MUST be raw strings inside the JSON.
- If the error is a missing directory, include `import os` if needed and add `os.makedirs()`.

Other rules:
- If the error mentions "No module named 'X'", use pip_install with package "X" (use the real PyPI name)
- For syntax/logic errors, use patch_code.
"""

PYTHON_SUMMARY_SYSTEM = """\
You are a helpful assistant that interprets Python script results.

You will be given:
1. The user's original question/command
2. The raw output produced by executing a Python script that answers that question

Your job: produce a clear, concise natural-language answer to the user's question based on the output.
- Do NOT show raw Python code or script paths
- Format numbers, tables or lists in a readable way
- If the output contains an error, explain what went wrong in plain language
- Reply in the same language the user used (Chinese/English)
"""




def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _is_error_result(result: str) -> bool:
    """Heuristically detect error results."""
    lower = result.lower()
    if result.startswith("SecurityError:") or result.startswith("Error:") or result.startswith("OSError"):
        return True
    try:
        parsed = json.loads(result)
        if isinstance(parsed, dict):
            return parsed.get("status") in ("error", "no_results")
    except (json.JSONDecodeError, TypeError):
        pass
    return False


def _reflect(step: PlanStep, result: str, llm) -> tuple[str, str]:
    """
    Call LLM to self-evaluate whether the step should continue, retry, or abort.

    Returns: (verdict, reason)
    """
    user_msg = (
        f"Step: {step.description}\n"
        f"Tool: {step.tool}({json.dumps(step.args, ensure_ascii=False)})\n"
        f"Result (first 1000 chars): {result[:1000]}"
    )
    try:
        response = llm.invoke([
            SystemMessage(content=REFLECT_SYSTEM),
            HumanMessage(content=user_msg),
        ])
        raw = re.sub(r"<think>.*?</think>", "", response.content, flags=re.DOTALL).strip()
        if "```" in raw:
            parts = raw.split("```")
            raw = parts[1].lstrip("json").strip() if len(parts) >= 3 else raw
        parsed = json.loads(raw)
        verdict = parsed.get("verdict", "continue")
        reason = parsed.get("reason", "")
        return verdict, reason
    except Exception as e:
        logger.debug("Reflect parse failed: %s", e)
        # Fallback based on error detection
        if _is_error_result(result):
            return "retry", "Tool returned an error"
        return "continue", "auto-approved (reflect parse failed)"


class SkillExecutor:
    """
    Executes a plan step by step with:
    - Think → Act → Observe → Reflect loop per step
    - Cancellation token checked at every step boundary
    - Retry support (max _MAX_RETRIES per step)
    - Auto-fix for run_python errors (max _AUTO_FIX_MAX attempts)
    - Audit trail written to session manifest
    """

    def __init__(self, renderer: SkillRenderer, llm):
        self.renderer = renderer
        self.llm = llm

    def _auto_fix_python(
        self,
        script_path: str,
        error_output: str,
        tool_map: dict,
        original_command: str = "",
    ) -> tuple[bool, str]:
        """
        Attempt to auto-fix a failed Python script.

        Tries up to _AUTO_FIX_MAX times:
          1. Ask LLM to diagnose and suggest pip_install or fix_code
          2. Apply the fix
          3. Re-run via run_python

        Args:
            script_path: Path to the failing script.
            error_output: stderr / combined output from the failed run.
            tool_map: Dict of available tools (needs write_file).
            original_command: The user's original task description, used as a
                context anchor so the LLM doesn't drift from the script's intent.

        Returns (fixed: bool, final_result: str).
        """
        from kb_agent.tools.atomic.code_exec import pip_install, run_python

        # Read the original script content once and preserve it as an anchor.
        # Subsequent attempts always show the LLM the original intent, even if
        # a previous fix attempt already overwrote the file with wrong content.
        try:
            original_script_content = Path(script_path).read_text(encoding="utf-8")
        except Exception:
            original_script_content = "(could not read script)"

        # current_content tracks the last written version for re-run context
        current_content = original_script_content

        for attempt in range(1, _AUTO_FIX_MAX + 1):
            self.renderer.print_info(
                f"🔧 Auto-fix attempt {attempt}/{_AUTO_FIX_MAX} for {script_path}..."
            )

            # Ask LLM for repair action.
            # Convert file content to line-numbered version if this is a retry due to a failed patch
            if "PatchError" in error_output:
                lines = current_content.splitlines()
                numbered_content = "\n".join(f"{i+1:4d} | {line}" for i, line in enumerate(lines))
                content_to_show = f"FILE CONTENT WITH LINE NUMBERS:\n{numbered_content}"
            else:
                content_to_show = f"Current script content:\n```python\n{current_content[:3000]}\n```"

            task_ctx = f"Original user task: {original_command}\n\n" if original_command else ""
            user_msg = (
                f"{task_ctx}"
                f"Script path: {script_path}\n"
                f"{content_to_show}\n\n"
                f"Error output:\n{error_output[:2000]}"
            )
            try:
                response = self.llm.invoke([
                    SystemMessage(content=AUTO_FIX_SYSTEM),
                    HumanMessage(content=user_msg),
                ])
                raw = re.sub(r"<think>.*?</think>", "", response.content, flags=re.DOTALL).strip()
                
                # Extract JSON block
                json_match = re.search(r"\{.*?\}", raw, re.DOTALL)
                if not json_match:
                    raise ValueError("No JSON object found")
                fix = json.loads(json_match.group(0))
                        
            except Exception as e:
                self.renderer.print_info(f"Auto-fix parse failed: {e}")
                break

            action = fix.get("action", "give_up")

            if action == "give_up":
                self.renderer.print_info("Auto-fix: no remedy found, giving up.")
                break

            elif action == "pip_install":
                pkg = fix.get("package", "")
                if not pkg:
                    break
                self.renderer.print_info(f"Auto-fix: installing '{pkg}' via pip...")
                exit_code, pip_out = pip_install(pkg)
                self.renderer.print_observe(pip_out[:500], is_error=(exit_code != 0))
                if exit_code != 0:
                    self.renderer.print_info("pip install failed, giving up.")
                    break

            elif action == "patch_code":
                search_block = fix.get("search_block", "")
                replace_block = fix.get("replace_block", "")
                if not search_block:
                    break
                
                self.renderer.print_info("Auto-fix: applying surgical patch...")
                if search_block not in current_content:
                    # Fallback validation loop: target block not found!
                    error_output = (
                        "PatchError: The exact search_block was not found in the file. "
                        "Make sure your indentation perfectly matches the file, and do not use line numbers in your search_block!\n"
                        f"You searched for:\n{search_block}"
                    )
                    self.renderer.print_info(f"Patch validation failed. Forcing LLM retry.")
                    continue

                fixed_code = current_content.replace(search_block, replace_block)

                write_fn = tool_map.get("write_file")
                if write_fn is None:
                    break
                write_result = str(write_fn.invoke({
                    "path": script_path,
                    "content": fixed_code,
                    "mode": "overwrite",
                }))
                self.renderer.print_observe(write_result[:200])
                current_content = fixed_code  # track latest written version

            else:
                break

            # Re-run the script
            rerun_result = str(run_python.invoke({"script_path": script_path}))
            self.renderer.print_observe(rerun_result[:400])

            # Check if this run succeeded
            if "exit_code: 0" in rerun_result:
                return True, rerun_result

            # Update error output for next iteration.
            # NOTE: current_content is also updated above on fix_code, but we
            # deliberately do NOT update original_script_content — it always
            # reflects what the script was supposed to do.
            error_output = rerun_result

        return False, error_output

    def _summarise_python_result(self, command: str, raw_output: str) -> str:
        """
        Ask LLM to convert raw Python stdout/stderr into a natural-language answer.
        Falls back to the raw output on any LLM error.
        """
        if len(raw_output) < 2000:
            return raw_output
            
        try:
            user_msg = (
                f"User's question: {command}\n\n"
                f"Python script output:\n{raw_output[:4000]}"
            )
            response = self.llm.invoke([
                SystemMessage(content=PYTHON_SUMMARY_SYSTEM),
                HumanMessage(content=user_msg),
            ])
            summary = re.sub(r"<think>.*?</think>", "", response.content, flags=re.DOTALL).strip()
            return summary if summary else raw_output
        except Exception as e:
            logger.debug("Python result summarisation failed: %s", e)
            return raw_output

    def execute_plan(
        self,
        plan: list[PlanStep],
        session: Session,
        tool_map: dict[str, Any],
        cancel_token: CancellationToken,
    ) -> str:
        """
        Execute the plan. Returns the final accumulated result string.

        Args:
            plan: Ordered list of PlanStep objects.
            session: Active session for manifest writes.
            tool_map: Dict mapping tool name → @tool callable.
            cancel_token: Shared cancellation token.
        """
        total = len(plan)
        progress = self.renderer.make_progress(total)
        accumulated_results: list[str] = []
        # step_outputs: maps step_number -> result string for arg resolution
        step_outputs: dict[int, str] = {}
        idx = 0

        if progress:
            progress.start()
            task_id = progress.add_task("", total=total)

        try:
            while idx < len(plan):
                # ── Cancellation check at step boundary ──────────────────
                if cancel_token.is_set():
                    remaining = plan[idx:]
                    action = self.renderer.print_interrupt_menu(idx + 1, total)
                    cancel_token.reset()
                    action = self._handle_interrupt(
                        action, plan, idx, remaining, session, cancel_token
                    )
                    if action == "quit":
                        session.finish("aborted")
                        break
                    elif action == "skip":
                        record = StepRecord(
                            step_number=plan[idx].step_number,
                            tool=plan[idx].tool,
                            args=plan[idx].args,
                            status="skipped",
                            started_at=_now_iso(),
                            ended_at=_now_iso(),
                        )
                        session.add_step(record)
                        idx += 1
                        if progress:
                            progress.advance(task_id)
                        continue
                    elif action == "replanned":
                        # plan was modified in-place; restart from idx
                        total = len(plan)
                        continue
                    # else "continue" — fall through to execute

                step = plan[idx]
                self.renderer.print_step_header(step, total)

                result = self._execute_step(
                    step, session, tool_map, cancel_token, step_outputs
                )
                accumulated_results.append(result)
                step_outputs[step.step_number] = result

                idx += 1
                if progress:
                    progress.advance(task_id)

        finally:
            if progress:
                progress.stop()

        return "\n\n".join(accumulated_results) if accumulated_results else ""



    def _execute_step(
        self,
        step: PlanStep,
        session: Session,
        tool_map: dict[str, Any],
        cancel_token: CancellationToken,
        step_outputs: Optional[dict[int, str]] = None,
    ) -> str:
        """Execute a single step with Think→Act→Observe→Reflect and retry."""
        retry_count = 0
        result = ""
        step_outputs = step_outputs or {}

        while retry_count <= _MAX_RETRIES:
            started_at = _now_iso()

            # ── Think ─────────────────────────────────────────────────────────
            # Args are resolved upstream, directly use step.args
            resolved_args = step.args
            think_msg = f"Executing {step.tool} for: {step.description}"
            self.renderer.print_think(think_msg)

            # ── Act ───────────────────────────────────────────────────────
            self.renderer.print_act(step.tool, resolved_args)
            log_audit("skill_step_start", {"tool": step.tool, "args": resolved_args, "retry": retry_count})

            status = "failed"
            tool_fn = tool_map.get(step.tool)
            if tool_fn is None:
                result = f"Error: unknown tool '{step.tool}'"
                self.renderer.print_observe(result, is_error=True)
                break
            else:
                try:
                    result = str(tool_fn.invoke(resolved_args))
                except Exception as e:
                    result = f"Tool error ({step.tool}): {e}"

                # ── Auto-fix for run_python errors ───────────────────────
                if step.tool == "run_python" and "exit_code: 0" not in result:
                    script_path = resolved_args.get("script_path", "")
                    if script_path:
                        fixed, fixed_result = self._auto_fix_python(
                            script_path, result, tool_map,
                            original_command=session.command,
                        )
                        if fixed:
                            result = fixed_result

                # ── Observe ───────────────────────────────────────────────────
                is_error = _is_error_result(result)
                self.renderer.print_observe(result, is_error=is_error)
                ended_at = _now_iso()

                # ── Reflect ───────────────────────────────────────────────────
                if not is_error:
                    verdict, reason = "continue", "Auto-approved success result"
                    if step.tool in SAFE_READ_TOOLS and len(result) > 50:
                        self.renderer.print_info(f"[dim]⚡ Fast-pass reflection: skipped ({len(result)} chars)[/dim]")
                        log_audit("skill_step_reflect_skipped", {"tool": step.tool, "reason": "fast_pass", "length": len(result)})
                else:
                    verdict, reason = _reflect(step, result, self.llm)
                    self.renderer.print_reflect(verdict, reason)
                    log_audit("skill_step_reflect_forced", {"tool": step.tool, "verdict": verdict})

                if verdict == "continue" or retry_count >= _MAX_RETRIES:
                    status = "done" if verdict != "abort" else "failed"
                    break
                elif verdict == "retry":
                    retry_count += 1
                    status = "retried"
                    self.renderer.print_info(f"Retrying step {step.step_number} ({retry_count}/{_MAX_RETRIES})...")
                    continue
                else:  # abort
                    status = "failed"
                    break

        # ── Post-Python: LLM summary (Once per step, after all retries) ───────
        if step.tool == "run_python":
            # Replace raw result with LLM natural-language summary
            result = self._summarise_python_result(session.command, result)

        # Write audit record (use resolved_args if available)
        record = StepRecord(
            step_number=step.step_number,
            tool=step.tool,
            args=resolved_args if 'resolved_args' in dir() else step.args,
            status=status,
            started_at=started_at,
            ended_at=ended_at,
            result_summary=result[:500],
        )
        session.add_step(record)
        log_audit("skill_step_done", {"tool": step.tool, "status": status})

        return result

    def _handle_interrupt(
        self,
        action: str,
        plan: list[PlanStep],
        idx: int,
        remaining: list[PlanStep],
        session: Session,
        cancel_token: CancellationToken,
    ) -> str:
        """
        Handle interrupt menu choice. May mutate plan in-place for replan.

        Returns: "skip" | "continue" | "quit" | "replanned"
        """
        if action == "skip":
            return "skip"
        elif action == "continue":
            return "continue"
        elif action == "quit":
            return "quit"
        elif action == "replan":
            instruction = self.renderer.print_replan_prompt()
            revised = replan(remaining, instruction, session, self.llm)
            # Show revised plan for approval
            self.renderer.print_plan_table(revised)
            approval = self.renderer.print_approval_prompt()
            if approval == "q":
                return "quit"
            elif approval == "a":
                # Replace remaining steps in plan
                plan[idx:] = revised
                return "replanned"
            else:
                # 'e' — let them edit again (just continue for now)
                return "continue"
        return "continue"
