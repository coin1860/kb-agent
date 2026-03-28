"""
SkillShell — the interactive REPL for kb-cli.

Provides:
- Built-in commands: help/?, skills, exit/quit
- @ file picker: type @ to select a file from the input/ folder
- LLM-driven intent routing → two-layer milestone planning → approval gate → execution
- In-session command history via readline

Execution architecture:
  Milestone Planner: plan_milestones() decomposes the command into coarse goals.
  Milestone Executor: _execute_milestone() runs a focused Think–Act–Observe sub-loop
    per milestone, delegating to SkillExecutor._execute_step() for Reflect + retry + auto-fix.
  Legacy path: _legacy_execute_loop() preserved for debugging (flat single-level ReAct).
"""

from __future__ import annotations

import logging
import os
import readline  # noqa: F401  — side-effect: enables up-arrow history
from pathlib import Path
from typing import List, Optional

from rich.console import Console

from langchain_core.messages import HumanMessage, SystemMessage

from kb_agent.agent.tools import get_skill_tools
from kb_agent.audit import log_audit
from .executor import SkillExecutor
from .interruptor import CancellationToken, InterruptHandler
from .loader import SkillDef
from .planner import APPROVAL_TOOLS, Milestone, decide_next_step, generate_plan, replan
from .renderer import SkillRenderer
from .router import route_intent
from .session import Session, StepRecord



logger = logging.getLogger(__name__)

BUILTIN_COMMANDS = {"help", "?", "skills", "exit", "quit"}


class SkillShell:
    """
    Interactive REPL shell for kb-cli.

    All state lives in this object and the Session instance.
    No module-level globals — designed for future multi-session support.
    """

    def __init__(
        self,
        skills: dict[str, SkillDef],
        output_path: Path,
        python_code_path: Path,
        llm,
        console: Optional[Console] = None,
        input_path: Optional[Path] = None,
        temp_path: Optional[Path] = None,
    ):
        self.skills = skills
        self.output_path = output_path
        self.python_code_path = python_code_path
        self.input_path = input_path
        self.temp_path = temp_path
        self.llm = llm
        self.renderer = SkillRenderer(console or Console())
        self.session_history: list[str] = []  # bare command strings (for readline / help display)
        self._tool_list = get_skill_tools()
        self._tool_map = {t.name: t for t in self._tool_list}
        self._session: Optional[Session] = None

        # Read cli_max_iterations from settings (default 3)
        try:
            from kb_agent.config import settings as _cfg_settings
            self._cli_max_iterations: int = (
                _cfg_settings.cli_max_iterations
                if _cfg_settings and hasattr(_cfg_settings, "cli_max_iterations")
                else 3
            )
        except Exception:
            self._cli_max_iterations = 3

        # SkillExecutor is instantiated once and reused across milestone sub-loops
        # so Reflect/retry/auto-fix are available in the primary execution path.
        self._executor = SkillExecutor(renderer=self.renderer, llm=self.llm)

    # ──────────────────────────────────────────────────────────────────────
    # Public entry point
    # ──────────────────────────────────────────────────────────────────────

    def start(self, data_folder: Path) -> None:
        """Start the REPL loop."""
        # 0. Garbage collect old python_code and temp runs (> 24h)
        if self.python_code_path.exists():
            removed = Session.garbage_collect(self.python_code_path, days=1)
            if removed > 0:
                self.renderer.print_info(f"[dim]🧹 Cleaned up {removed} old run directories.[/dim]")

        self.renderer.print_banner(len(self.skills), data_folder)
        if self.input_path:
            self.renderer.print_info(
                f"[dim]📁 Input folder: {self.input_path}  "
                "(type [bold cyan]@[/bold cyan] to pick a file)[/dim]"
            )
        self._session = Session()
        self._session.setup_dirs(self.output_path, self.python_code_path, self.temp_path)

        # Build prompt_toolkit session once (None = fall back to plain input)
        pt_session = self._build_pt_session()

        while True:
            try:
                command = self._read_command(pt_session)
            except (EOFError, KeyboardInterrupt):
                self.renderer.print_info("\nExiting kb-cli.")
                if self._session:
                    self._session.finish("completed")
                break

            if command is None:
                # Ctrl-D / EOF handled inside _read_command
                if self._session:
                    self._session.finish("completed")
                break

            if not command:
                continue

            self.session_history.append(command)

            if command.lower() in {"exit", "quit"}:
                self.renderer.print_info("Goodbye.")
                if self._session:
                    self._session.finish("completed")
                break
            elif command.lower() in {"help", "?"}:
                self._show_help()
            elif command.lower() == "skills":
                self.renderer.print_skills_table(self.skills)
            else:
                self._run_command(command)


    # ──────────────────────────────────────────────────────────────────────
    # Input helpers — @ file picker via prompt_toolkit
    # ──────────────────────────────────────────────────────────────────────

    def _list_input_files(self) -> List[str]:
        """Return sorted filenames from input_path (no paths)."""
        if not self.input_path or not self.input_path.exists():
            return []
        return sorted(
            f.name for f in self.input_path.iterdir()
            if f.is_file() and not f.name.startswith(".")
        )

    def _build_pt_session(self):
        """
        Build a prompt_toolkit PromptSession with an @ file completer.

        The completer fires as soon as '@' is the first character of the
        current word (complete_while_typing=True), showing all filenames
        from input_path. The user navigates with Tab/Up/Down and confirms
        with Enter — no separate step needed.

        Returns a PromptSession, or None if prompt_toolkit is unavailable.
        """
        try:
            from prompt_toolkit import PromptSession
            from prompt_toolkit.completion import Completer, Completion
            from prompt_toolkit.history import InMemoryHistory

            input_path = self.input_path  # captured for closure

            class _AtFileCompleter(Completer):
                """Complete @<filename> tokens from the input/ folder."""

                def get_completions(self, document, complete_event):
                    # Extract the current token before the cursor manually
                    text = document.text_before_cursor
                    # Find last whitespace-delimited token
                    parts = text.split()
                    if not parts:
                        return
                    word = parts[-1]
                    # Only activate when token starts with '@'
                    if not word.startswith("@"):
                        return
                    needle = word[1:]  # text after '@'
                    if input_path and input_path.exists():
                        for f in sorted(input_path.iterdir()):
                            if f.is_file() and not f.name.startswith("."):
                                if f.name.lower().startswith(needle.lower()):
                                    yield Completion(
                                        "@" + f.name,
                                        start_position=-len(word),
                                        display=f.name,
                                        display_meta="input/",
                                    )

            return PromptSession(
                completer=_AtFileCompleter(),
                complete_while_typing=True,
                history=InMemoryHistory(),
            )
        except ImportError:
            return None

    def _read_command(self, pt_session=None) -> Optional[str]:
        """
        Read a command from the user.

        - With prompt_toolkit: typing '@' immediately shows a live file
          dropdown from input/; Tab/Up/Down selects; Enter confirms.
        - Without prompt_toolkit: plain input() with a numbered fallback
          list shown when user types '@' and presses Enter.
        Returns None on EOF.
        """
        prompt_str = "\n[kb-cli]> "
        if pt_session is not None:
            try:
                raw = pt_session.prompt(prompt_str).strip()
                return raw if raw else ""
            except EOFError:
                return None
        else:
            # Plain fallback
            try:
                raw = input(prompt_str).strip()
            except EOFError:
                return None
            # Bare '@' in fallback mode: show numbered list
            if raw == "@" and self.input_path:
                files = self._list_input_files()
                if files:
                    print("")  # spacer
                    for i, name in enumerate(files, 1):
                        print(f"  {i}. {name}")
                    sel = input("Select file number (or Enter to cancel): ").strip()
                    if sel.isdigit():
                        idx = int(sel) - 1
                        if 0 <= idx < len(files):
                            return "@" + files[idx]
                return ""
            return raw

    # ──────────────────────────────────────────────────────────────────────
    # Command routing and execution
    # ──────────────────────────────────────────────────────────────────────

    def _resolve_at_refs(self, command: str) -> str:
        """
        Replace every @filename token in command with its full absolute path
        from input_path.  Unknown @tokens are left unchanged.
        """
        if not self.input_path or "@" not in command:
            return command
        import re
        def _replace(m: re.Match) -> str:
            name = m.group(1)            # bare filename after '@'
            candidate = self.input_path / name  # type: ignore[operator]
            if candidate.exists():
                return str(candidate)
            return m.group(0)             # leave unchanged if not found
        return re.sub(r"@(\S+)", _replace, command)

    def _run_command(self, command: str) -> None:
        """Route and execute a user command."""
        assert self._session is not None

        # Resolve @filename → absolute path before sending to LLM
        resolved = self._resolve_at_refs(command)
        if resolved != command:
            self.renderer.print_info(f"[dim]📎 Resolved: {resolved}[/dim]")

        # Store resolved command so executor references the real path in LLM summary
        self._session.command = resolved

        # 1. Routing, Intent Preview, and Milestone Planning
        self.renderer.print_info("🔍 Analyzing intent and planning...")
        from .planner import generate_unified_plan
        unified_plan = generate_unified_plan(
            command=resolved,
            session=self._session,
            skills=self.skills,
            llm=self.llm,
            default_budget=self._cli_max_iterations
        )

        route_type = unified_plan.route
        skill_id = unified_plan.skill_id
        summary = unified_plan.summary
        has_write_ops = unified_plan.has_write_ops
        milestones = unified_plan.milestones

        # ── Chitchat shortcut ───────────────
        if route_type == "chitchat":
            self.renderer.print_info("[dim]💬 Direct response[/dim]")
            answer = summary
            self.renderer.print_result(answer, title="Reply")
            log_audit("chitchat_response", {"command": resolved[:200]})
            return

        # ── Skill / free_agent ──
        skill_def: Optional[SkillDef] = None
        if route_type == "skill" and skill_id:
            skill_def = self.skills.get(skill_id)
            self.renderer.print_info(f"🧩 Matched skill: [cyan]{skill_id}[/cyan]")
            self._session.skill_name = skill_id

        # 2. Print intent preview
        self.renderer.print_intent_preview(summary, has_write_ops)

        # 3. Intent approval (auto-approve if read-only)
        approved = self.renderer.print_intent_approval(has_write_ops)
        if not approved:
            self.renderer.print_info("Cancelled.")
            return

        # 4. Dynamic execution loop
        cancel_token = CancellationToken()
        log_audit("dynamic_execute_start", {
            "command": resolved[:200],
            "route": route_type,
            "skill": skill_def.name if skill_def else None,
        })
        self._session.write_manifest()

        try:
            with InterruptHandler(cancel_token):
                result = self._milestone_execute_loop(
                    command=resolved,
                    milestones=milestones,
                    skill_def=skill_def,
                    session=self._session,
                    cancel_token=cancel_token
                )
            if result:
                self.renderer.print_result(result, title="Answer")
            log_audit("milestone_execute_done", {"command": resolved[:200]})
        finally:
            self._session.cleanup()

    # TODO: remove legacy loop after 2-week bake period
    def _legacy_execute_loop(
        self,
        command: str,
        skill_def: Optional[SkillDef],
        session: Session,
        cancel_token: CancellationToken,
    ) -> str:
        """
        [LEGACY] Flat single-level ReAct loop: decide_next_step → execute → repeat.

        Preserved for debugging.  Primary path now uses _milestone_execute_loop().
        """
        from datetime import datetime, timezone

        tool_history: list[dict] = []
        max_iter = self._cli_max_iterations
        final_answer = ""

        for iteration in range(1, max_iter + 2):  # +1 extra for forced final_answer pass
            # ── Cancellation check ────────────────────────────────────────
            if cancel_token.is_set():
                cancel_token.reset()
                self.renderer.print_info("⏸ Interrupted — stopping execution.")
                break

            # ── Decide next action ────────────────────────────────────────
            action = decide_next_step(
                command=command,
                session=session,
                llm=self.llm,
                skill_def=skill_def,
                tool_history=tool_history,
                iteration=iteration,
                max_iterations=max_iter,
            )

            action_type = action.get("action", "final_answer")
            reason = action.get("reason", "")

            # ── Final answer ──────────────────────────────────────────────
            if action_type == "final_answer":
                final_answer = action.get("answer", "")
                break

            # ── Tool call ─────────────────────────────────────────────────
            tool_name = action.get("tool", "")
            args = action.get("args", {})
            tool_call_id = action.get("tool_call_id", f"call_legacy_i{iteration}")

            self.renderer.print_dynamic_step_header(iteration, max_iter, reason)
            self.renderer.print_think(reason or f"Calling {tool_name}")
            self.renderer.print_act(tool_name, args)

            # Per-step approval for write ops
            if tool_name in APPROVAL_TOOLS:
                from rich.prompt import Prompt
                raw = Prompt.ask(
                    f"[bold yellow]⚠️  {tool_name} requires approval. Proceed?[/bold yellow] "
                    "[dim]([bold white]Y[/bold white]es / [bold white]N[/bold white]o)[/dim]",
                    choices=["y", "n"],
                    default="y",
                    show_choices=False,
                ).lower()
                if raw != "y":
                    self.renderer.print_info(f"Skipped {tool_name}.")
                    tool_history.append({
                        "step": iteration, "tool": tool_name, "args": args,
                        "result": "[user skipped]", "status": "skipped",
                        "tool_call_id": tool_call_id,
                    })
                    continue

            tool_fn = self._tool_map.get(tool_name)
            started_at = datetime.now(timezone.utc).isoformat()
            if tool_fn is None:
                result_str = f"Error: unknown tool '{tool_name}'"
                status = "error"
                self.renderer.print_observe(result_str, is_error=True)
            else:
                try:
                    result_str = str(tool_fn.invoke(args))
                    status = "success"
                except Exception as e:
                    result_str = f"Tool error ({tool_name}): {e}"
                    status = "error"
                self.renderer.print_observe(result_str, is_error=(status == "error"))

            # Write audit record
            record = StepRecord(
                step_number=len(session.steps) + 1,
                tool=tool_name,
                args=args,
                status=status,
                started_at=started_at,
                ended_at=datetime.now(timezone.utc).isoformat(),
                result_summary=result_str[:500],
            )
            session.add_step(record)
            log_audit("dynamic_step_done", {"tool": tool_name, "status": status})

            tool_history.append({
                "step": iteration,
                "tool": tool_name,
                "args": args,
                "result": result_str,
                "status": status,
                "tool_call_id": tool_call_id,
            })

        return final_answer

    # ──────────────────────────────────────────────────────────────────────
    # Two-layer milestone execution  (primary path)
    # ──────────────────────────────────────────────────────────────────────

    _COMPRESS_SYSTEM = """\
You are a milestone summariser for an AI agent. Given a milestone goal and the raw
tool outputs produced during that milestone, write a comprehensive summary (up to 4,000 tokens)
that:
- States what was done and what was found
- Preserves ALL structured artefacts exactly: file paths, ticket IDs, numbers, URLs, and data snippets
- Retains as much useful detail as possible from the raw output, condensing only the fluff

This summary will be passed as context to subsequent milestones.
"""

    def _compress_milestone_result(
        self,
        milestone: Milestone,
        raw_result: str,
        llm,
    ) -> str:
        """
        Compress a milestone's raw output into a ≤200-token paragraph summary.

        Falls back to raw_result[:1000] (truncated at last newline) on LLM error.
        """
        try:
            # We pass a larger chunk of raw output since the model can handle it
            user_msg = (
                f"Milestone goal: {milestone.goal}\n\n"
                f"Raw output:\n{raw_result[:40000]}"
            )
            resp = llm.invoke([
                SystemMessage(content=self._COMPRESS_SYSTEM),
                HumanMessage(content=user_msg),
            ])
            summary = resp.content.strip()
            usage = getattr(resp, "usage_metadata", None)
            if usage:
                logger.debug(
                    "Milestone compression: %d output tokens",
                    usage.get("output_tokens", 0),
                )
            return summary if summary else raw_result[:1000]
        except Exception as e:
            logger.warning("_compress_milestone_result failed: %s", e)
            # Truncate at last newline within first 1000 chars
            chunk = raw_result[:1000]
            nl = chunk.rfind("\n")
            return chunk[:nl] if nl > 0 else chunk

    def _execute_milestone(
        self,
        milestone: Milestone,
        prior_context: str,
        session: Session,
        cancel_token: CancellationToken,
        command: str,
        skill_def: Optional[SkillDef],
        milestone_index: int,
    ) -> str:
        """
        Run a focused Think\u2013Act\u2013Observe sub-loop for a single milestone.

        Delegates individual step execution to SkillExecutor._execute_step() so
        that Reflect, retry, and Python auto-fix are active in the primary path.

        Returns the raw result string from the milestone (before compression).
        """
        from .planner import PlanStep

        # Initialise tool history from all previous session steps to provide cumulative context
        tool_history: list[dict] = [
            {
                "step": srec.step_number,
                "tool": srec.tool,
                "args": srec.args,
                "result": srec.result_summary,
                "status": srec.status,
            }
            for srec in session.steps
        ]
        max_iter = milestone.iteration_budget
        milestone_result = ""

        self.renderer.print_info(
            f"\n[bold cyan]\U0001f3af Milestone {milestone_index}: {milestone.goal}[/bold cyan]"
        )
        self.renderer.print_info(f"[dim]Expected: {milestone.expected_output}[/dim]")

        for iteration in range(1, max_iter + 2):  # +1 for forced final_answer pass
            # ── Cancellation check ────────────────────────────────────────
            if cancel_token.is_set():
                cancel_token.reset()
                self.renderer.print_info("⏸ Interrupted — stopping milestone.")
                break

            # ── Decide next action (milestone-focused) ────────────────────
            action = decide_next_step(
                command=command,
                session=session,
                llm=self.llm,
                skill_def=skill_def,
                tool_history=tool_history,
                iteration=iteration,
                max_iterations=max_iter,
                milestone_goal=milestone.goal,
                prior_context=prior_context or None,
            )

            action_type = action.get("action", "final_answer")
            reason = action.get("reason", "")

            # ── Milestone done ────────────────────────────────────────────
            if action_type == "final_answer":
                milestone_result = action.get("answer", "")
                break

            # ── Tool call ─────────────────────────────────────────────────
            tool_name = action.get("tool", "")
            args = action.get("args", {})
            finish_flag = action.get("finish_milestone", False)
            tool_call_id = action.get("tool_call_id", f"call_m{milestone_index}_i{iteration}")

            self.renderer.print_dynamic_step_header(iteration, max_iter, reason)

            # Per-step approval for write ops
            if tool_name in APPROVAL_TOOLS:
                from rich.prompt import Prompt
                raw_ans = Prompt.ask(
                    f"[bold yellow]⚠️  {tool_name} requires approval. Proceed?[/bold yellow] "
                    "[dim]([bold white]Y[/bold white]es / [bold white]N[/bold white]o)[/dim]",
                    choices=["y", "n"],
                    default="y",
                    show_choices=False,
                ).lower()
                if raw_ans != "y":
                    self.renderer.print_info(f"Skipped {tool_name}.")
                    tool_history.append({
                        "step": iteration, "tool": tool_name, "args": args,
                        "result": "[user skipped]", "status": "skipped",
                        "tool_call_id": tool_call_id,
                    })
                    # Skipped steps do NOT advance iteration count
                    continue

            # Build a transient PlanStep so SkillExecutor._execute_step() can
            # apply Reflect + retry + Python auto-fix.
            step = PlanStep(
                step_number=len(session.steps) + 1,
                description=reason or f"Call {tool_name} (milestone: {milestone.goal[:60]})",
                tool=tool_name,
                args=args,
                requires_approval=(tool_name in APPROVAL_TOOLS),
            )

            # Delegate to SkillExecutor — this gives us Reflect, retry, auto-fix
            step_outputs: dict = {}  # no cross-step arg resolution needed here
            result_str = self._executor._execute_step(
                step=step,
                session=session,
                tool_map=self._tool_map,
                cancel_token=cancel_token,
                step_outputs=step_outputs,
            )

            tool_history.append({
                "step": iteration,
                "tool": tool_name,
                "args": args,
                "result": result_str,
                "status": "success",
                "tool_call_id": tool_call_id,
            })
            log_audit("milestone_step_done", {"tool": tool_name, "milestone": milestone_index})

            if finish_flag:
                self.renderer.print_info("[dim]🎯 Milestone finish flag received, terminating early.[/dim]")
                milestone_result = result_str
                break

        return milestone_result

    def _milestone_execute_loop(
        self,
        command: str,
        milestones: list,
        skill_def: Optional[SkillDef],
        session: Session,
        cancel_token: CancellationToken,
    ) -> str:
        """
        Two-layer execution: Milestone Planner \u2192 per-milestone sub-loops.

        1. plan_milestones() has already decomposed the command into coarse goals.
        2. _execute_milestone() runs a focused sub-loop per milestone,
           delegating to SkillExecutor._execute_step() for resilience.
        3. _compress_milestone_result() distils each result for the next milestone.

        Returns the final accumulated answer string.
        """
        log_audit("milestone_execute_start", {
            "command": command[:200],
            "skill": skill_def.name if skill_def else None,
        })

        # ── Step 1: Milestones received ─────────────────────────────


        self.renderer.print_info(
            f"[dim]📋 Plan: {len(milestones)} milestone(s)[/dim]"
        )
        for i, m in enumerate(milestones, 1):
            self.renderer.print_info(f"[dim]  {i}. {m.goal}[/dim]")

        # ── Step 2: Execute each milestone ────────────────────────────────
        prior_context = ""
        final_results: list[str] = []

        for i, milestone in enumerate(milestones, 1):
            if cancel_token.is_set():
                self.renderer.print_info("⏸ Interrupted — halting remaining milestones.")
                break

            raw_result = self._execute_milestone(
                milestone=milestone,
                prior_context=prior_context,
                session=session,
                cancel_token=cancel_token,
                command=command,
                skill_def=skill_def,
                milestone_index=i,
            )
            final_results.append(raw_result)

            # ── Compress and forward context to next milestone ─────────────
            if i < len(milestones):
                if len(raw_result) < 8000:
                    compressed = raw_result
                    self.renderer.print_info(f"[dim]⚡ Fast-pass context: bypassed compression ({len(raw_result)} chars)[/dim]")
                    logger.debug("Milestone %d result under 8k chars, skipping compression", i)
                else:
                    compressed = self._compress_milestone_result(milestone, raw_result, self.llm)
                    logger.debug("Milestone %d compressed to %d chars", i, len(compressed))
                
                label = f"[Milestone {i}: {milestone.goal}]\n{compressed}"
                prior_context = (prior_context + "\n\n" + label).strip() if prior_context else label

            # ── Audit milestone completion ─────────────────────────────────
            log_audit("milestone_done", {
                "index": i,
                "goal": milestone.goal[:80],
                "result_len": len(raw_result),
            })

        # Return the last milestone's result as the final answer
        return final_results[-1] if final_results else ""

    def _intent_approval(self, preview: dict) -> bool:
        """Show intent preview and prompt user for approval. Returns True if approved."""
        self.renderer.print_intent_preview(preview["summary"], preview.get("has_write_ops", False))
        return self.renderer.print_intent_approval(preview.get("has_write_ops", False))

    def _approval_gate(self, plan: list) -> Optional[list]:
        """
        Show plan and request approval if any step requires it.

        Returns the (possibly revised) plan, or None if user quits.
        """
        has_sensitive = any(s.requires_approval for s in plan)

        if not has_sensitive:
            # Auto-approve read-only plan
            self.renderer.print_plan_table(plan)
            self.renderer.print_info("[dim]✓ Auto-approved (read-only plan)[/dim]")
            return plan

        while True:
            self.renderer.print_plan_table(plan)
            choice = self.renderer.print_approval_prompt()

            if choice == "approve":
                return plan
            elif choice == "quit":
                self.renderer.print_info("Cancelled.")
                return None
            elif choice == "edit":
                instruction = self.renderer.print_replan_prompt()
                plan = replan(plan, instruction, self._session, self.llm)
                # Loop back to show revised plan

    # ──────────────────────────────────────────────────────────────────────
    # Help
    # ──────────────────────────────────────────────────────────────────────

    def _show_help(self) -> None:
        from rich.table import Table
        from rich import box
        table = Table("Command", "Description", box=box.SIMPLE, header_style="bold cyan")
        table.add_row("help / ?", "Show this help")
        table.add_row("skills", "List all loaded skill playbooks")
        table.add_row("exit / quit", "Exit kb-cli")
        table.add_row("<any other text>", "Routed to LLM agent for planning and execution")
        self.renderer.console.print(table)
        if self.skills:
            self.renderer.console.print("\n[bold]Loaded skills:[/bold]")
            self.renderer.print_skills_table(self.skills)
