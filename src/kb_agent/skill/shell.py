"""
SkillShell — the interactive REPL for kb-cli.

Provides:
- Built-in commands: help/?, skills, exit/quit
- @ file picker: type @ to select a file from the input/ folder
- LLM-driven intent routing → plan generation → approval gate → execution
- In-session command history via readline
"""

from __future__ import annotations

import logging
import os
import readline  # noqa: F401  — side-effect: enables up-arrow history
from pathlib import Path
from typing import List, Optional

from rich.console import Console

from kb_agent.agent.tools import get_skill_tools
from kb_agent.audit import log_audit
from .executor import SkillExecutor
from .interruptor import CancellationToken, InterruptHandler
from .loader import SkillDef
from .planner import generate_plan, replan
from .renderer import SkillRenderer
from .router import route_intent
from .session import Session

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
    ):
        self.skills = skills
        self.output_path = output_path
        self.python_code_path = python_code_path
        self.input_path = input_path
        self.llm = llm
        self.renderer = SkillRenderer(console or Console())
        self.session_history: list[str] = []  # in-memory for this session only
        self._tool_list = get_skill_tools()
        self._tool_map = {t.name: t for t in self._tool_list}
        self._session: Optional[Session] = None

    # ──────────────────────────────────────────────────────────────────────
    # Public entry point
    # ──────────────────────────────────────────────────────────────────────

    def start(self, data_folder: Path) -> None:
        """Start the REPL loop."""
        self.renderer.print_banner(len(self.skills), data_folder)
        if self.input_path:
            self.renderer.print_info(
                f"[dim]📁 Input folder: {self.input_path}  "
                "(type [bold cyan]@[/bold cyan] to pick a file)[/dim]"
            )
        self._session = Session()
        self._session.setup_dirs(self.output_path, self.python_code_path)

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

        # 1. Route intent
        self.renderer.print_info("🔍 Routing intent...")
        route = route_intent(resolved, self.skills, self.llm)

        skill_def: Optional[SkillDef] = None
        if route.route == "skill" and route.skill_id:
            skill_def = self.skills.get(route.skill_id)
            self.renderer.print_info(f"🧩 Matched skill: [cyan]{route.skill_id}[/cyan]")
            self._session.skill_name = route.skill_id
        else:
            self.renderer.print_info("🤖 Free-agent mode — generating plan...")

        # 2. Generate plan (use resolved command so LLM gets real path)
        plan = generate_plan(resolved, self._session, self.llm, skill_def)

        if not plan:
            self.renderer.print_error("Could not generate a plan for this command.")
            return

        # 3. Approval gate
        plan = self._approval_gate(plan)
        if plan is None:
            return  # User quit

        # 4. Execute plan with interrupt support
        cancel_token = CancellationToken()
        executor = SkillExecutor(self.renderer, self.llm)

        log_audit("skill_execute_start", {"command": command[:200], "steps": len(plan)})
        self._session.write_manifest()

        try:
            with InterruptHandler(cancel_token):
                result = executor.execute_plan(plan, self._session, self._tool_map, cancel_token)

            # 5. Show result
            if result:
                self.renderer.print_result(result, title="Execution Complete")

            log_audit("skill_execute_done", {"command": command[:200]})
        finally:
            # Deep clean session resources (e.g. python_code folders)
            self._session.cleanup()

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
