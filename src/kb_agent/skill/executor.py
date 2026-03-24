"""
Skill executor — runs a plan step-by-step with Think/Act/Observe/Reflect,
cancellation-token-based interrupt support, and step audit trail.
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
  → set "package" to the pip package name to install
- "fix_code": the code itself has a bug that can be fixed
  → set "fixed_code" to the complete corrected Python script (not a diff, the full file)
- "give_up": the error is unrecoverable or unclear

Rules:
- If the error mentions "No module named 'X'", use pip_install with package "X" (use the real PyPI name if different from the import name)
- For syntax/logic errors, fix_code with the complete corrected script
- Never pip_install and fix_code in the same response — pick one
- The fixed_code must be complete and runnable, not a partial patch

Respond ONLY with valid JSON:
{"action": "pip_install"|"fix_code"|"give_up", "package": "...", "fixed_code": "..."}
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

_AUTO_FIX_MAX = 3

RESOLVE_ARGS_SYSTEM = """\
You are a tool argument resolver for a multi-step task executor.

You will be given:
1. The current step description and its planned args (which may contain placeholder references like {search_results})
2. The outputs from all previous steps

Your job: produce the CONCRETE args dict for this step by:
- Replacing any placeholder references with the actual content from previous steps
- Synthesizing/formatting content from previous step outputs as needed (e.g., converting raw JSON search results into nicely formatted Markdown)
- Keeping any args that are already concrete values unchanged

IMPORTANT rules:
- For write_file: the 'content' field must be the actual formatted content to write (in Markdown if appropriate), NOT a placeholder
- For run_python: the 'script_path' must be a real path
- Always include ALL required args for the tool — do not drop any

Respond with ONLY a valid JSON object of the resolved args. No other text.
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
    ) -> tuple[bool, str]:
        """
        Attempt to auto-fix a failed Python script.

        Tries up to _AUTO_FIX_MAX times:
          1. Ask LLM to diagnose and suggest pip_install or fix_code
          2. Apply the fix
          3. Re-run via run_python

        Returns (fixed: bool, final_result: str).
        """
        from kb_agent.tools.atomic.code_exec import pip_install, run_python

        # Read the current script content
        try:
            script_content = Path(script_path).read_text(encoding="utf-8")
        except Exception:
            script_content = "(could not read script)"

        for attempt in range(1, _AUTO_FIX_MAX + 1):
            self.renderer.print_info(
                f"🔧 Auto-fix attempt {attempt}/{_AUTO_FIX_MAX} for {script_path}..."
            )

            # Ask LLM for repair action
            user_msg = (
                f"Script path: {script_path}\n"
                f"Script content:\n```python\n{script_content[:3000]}\n```\n\n"
                f"Error output:\n{error_output[:2000]}"
            )
            try:
                response = self.llm.invoke([
                    SystemMessage(content=AUTO_FIX_SYSTEM),
                    HumanMessage(content=user_msg),
                ])
                raw = re.sub(r"<think>.*?</think>", "", response.content, flags=re.DOTALL).strip()
                if "```" in raw:
                    parts = raw.split("```")
                    raw = parts[1].lstrip("json").strip() if len(parts) >= 3 else raw
                fix = json.loads(raw)
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

            elif action == "fix_code":
                fixed_code = fix.get("fixed_code", "")
                if not fixed_code:
                    break
                self.renderer.print_info("Auto-fix: rewriting script...")
                write_fn = tool_map.get("write_file")
                if write_fn is None:
                    break
                # Use output/ path for the script since it was written there by write_file earlier
                write_result = str(write_fn.invoke({
                    "path": script_path,
                    "content": fixed_code,
                    "mode": "overwrite",
                }))
                self.renderer.print_observe(write_result[:200])
                script_content = fixed_code

            else:
                break

            # Re-run the script
            rerun_result = str(run_python.invoke({"script_path": script_path}))
            self.renderer.print_observe(rerun_result[:400])

            # Check if this run succeeded
            if "exit_code: 0" in rerun_result:
                return True, rerun_result

            # Extract error output for next iteration
            error_output = rerun_result
            # Update script_content if it was changed
            try:
                script_content = Path(script_path).read_text(encoding="utf-8")
            except Exception:
                pass

        return False, error_output

    def _summarise_python_result(self, command: str, raw_output: str) -> str:
        """
        Ask LLM to convert raw Python stdout/stderr into a natural-language answer.
        Falls back to the raw output on any LLM error.
        """
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

    def _resolve_args(
        self,
        step: PlanStep,
        step_outputs: dict[int, str],
    ) -> dict:
        """
        Use LLM to resolve concrete args for this step.

        Only invoked when:
        - There are previous step outputs available, AND
        - The step has args that might contain placeholder references OR
          the step requires content generated from previous steps (e.g. write_file).
        """
        args_str = json.dumps(step.args, ensure_ascii=False)

        # Check if we even need resolution: does args_str contain placeholders
        # or is this a write/run step that depends on prior output?
        needs_resolution = (
            "{" in args_str
            or step.tool in ("write_file", "run_python")
        ) and bool(step_outputs)

        if not needs_resolution:
            return step.args

        # Build context from prior steps
        context_parts = []
        for step_num, output in sorted(step_outputs.items()):
            # Limit each prior output to 3000 chars to keep prompt manageable
            context_parts.append(f"Step {step_num} output:\n{output[:3000]}")
        context_str = "\n\n".join(context_parts)

        user_msg = (
            f"Current step: {step.description}\n"
            f"Tool: {step.tool}\n"
            f"Planned args: {args_str}\n\n"
            f"Previous step outputs:\n{context_str}"
        )

        try:
            response = self.llm.invoke([
                SystemMessage(content=RESOLVE_ARGS_SYSTEM),
                HumanMessage(content=user_msg),
            ])
            raw = re.sub(r"<think>.*?</think>", "", response.content, flags=re.DOTALL).strip()
            if "```" in raw:
                parts = raw.split("```")
                raw = parts[1].lstrip("json").strip() if len(parts) >= 3 else raw
            resolved = json.loads(raw)
            if isinstance(resolved, dict):
                logger.debug("Resolved args for %s: %s", step.tool, list(resolved.keys()))
                return resolved
        except Exception as e:
            logger.warning("Arg resolution failed for step %d (%s): %s", step.step_number, step.tool, e)

        return step.args  # Fall back to original args on failure

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

            # ── Think: resolve actual args from prior step outputs ────────
            resolved_args = self._resolve_args(step, step_outputs)
            think_msg = (
                f"Executing {step.tool} for: {step.description}"
                + (" (args resolved from prior outputs)" if resolved_args != step.args else "")
            )
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
                            script_path, result, tool_map
                        )
                        if fixed:
                            result = fixed_result

                # ── Observe ───────────────────────────────────────────────────
                is_error = _is_error_result(result)
                self.renderer.print_observe(result, is_error=is_error)
                ended_at = _now_iso()

                # ── Reflect ───────────────────────────────────────────────────
                verdict, reason = _reflect(step, result, self.llm)
                self.renderer.print_reflect(verdict, reason)

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
