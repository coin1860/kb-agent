"""
Rich-based CLI renderer for the skill agent.

Provides Think/Act/Observe/Reflect logging, plan tables,
progress bars, result panels, and interrupt menus.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Optional

from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel
from rich.progress import BarColumn, Progress, SpinnerColumn, TextColumn, TimeElapsedColumn
from rich.prompt import Prompt
from rich.table import Table
from rich import box

from .planner import PlanStep


from rich.markup import escape


class SkillRenderer:
    """Renders all kb-cli CLI output using Rich."""

    def __init__(self, console: Optional[Console] = None):
        self.console = console or Console()

    # ──────────────────────────────────────────────────────────────────────
    # Startup
    # ──────────────────────────────────────────────────────────────────────

    def print_banner(self, skill_count: int, data_folder: Path) -> None:
        """Print the startup banner."""
        content = (
            f"[bold cyan]KB-Cli Agent[/bold cyan]  🧩  "
            f"[dim]{skill_count} skill{'s' if skill_count != 1 else ''} loaded[/dim]  │  "
            f"[dim]Data: {data_folder}[/dim]\n"
            f"[dim]Type a command, 'skills' to list, or 'exit' to quit.[/dim]"
        )
        self.console.print(Panel(content, border_style="cyan", padding=(0, 1)))

    # ──────────────────────────────────────────────────────────────────────
    # Plan display
    # ──────────────────────────────────────────────────────────────────────

    def print_plan_table(self, steps: list[PlanStep]) -> None:
        """Print the execution plan as a Rich table."""
        table = Table(
            "#", "Tool", "Description", "Approval",
            box=box.ROUNDED,
            border_style="dim",
            show_lines=False,
            header_style="bold white",
        )
        for step in steps:
            approval_icon = "[bold red]🔒 Required[/]" if step.requires_approval else "[dim]✓ Auto[/]"
            table.add_row(
                str(step.step_number),
                f"[cyan]{step.tool}[/cyan]",
                step.description,
                approval_icon,
            )
        self.console.print("\n[bold]📋 Execution Plan:[/bold]")
        self.console.print(table)

    # ──────────────────────────────────────────────────────────────────────
    # Think / Act / Observe / Reflect
    # ──────────────────────────────────────────────────────────────────────

    def print_think(self, text: str) -> None:
        """Print agent's reasoning (dim gray)."""
        self.console.print(f"[dim]💭 Think:[/] [dim italic]{escape(text[:300])}[/]")

    def print_act(self, tool: str, args: dict) -> None:
        """Print tool invocation (cyan)."""
        args_str = ", ".join(f"{k}={v!r}" for k, v in args.items())
        # args_str contains !r representations which already handle escaping quotes,
        # but path strings inside might still have brackets.
        self.console.print(f"[cyan]🔧 Act:[/][cyan]   {escape(tool)}({escape(args_str)})[/]")

    def print_observe(self, result: str, is_error: bool = False) -> None:
        """Print tool result summary (green/red)."""
        # result can be very long and contain many characters that look like markup
        preview = result[:400].replace("\n", " ") + ("…" if len(result) > 400 else "")
        color = "red" if is_error else "green"
        icon = "❌" if is_error else "📄"
        self.console.print(f"[{color}]{icon} Observe:[/] {escape(preview)}")

    def print_reflect(self, verdict: str, reason: str) -> None:
        """Print self-evaluation verdict (yellow)."""
        self.console.print(f"[yellow]🔁 Reflect:[/] [{escape(verdict)}] {escape(reason)}")


    # ──────────────────────────────────────────────────────────────────────
    # Progress
    # ──────────────────────────────────────────────────────────────────────

    def make_progress(self, total: int) -> Optional[Progress]:
        """Return a Rich Progress instance if total >= 3, else None."""
        if total < 3:
            return None
        return Progress(
            SpinnerColumn(),
            TextColumn("[bold cyan]Step {task.completed}/{task.total}"),
            BarColumn(),
            TimeElapsedColumn(),
            console=self.console,
            transient=False,
        )

    # ──────────────────────────────────────────────────────────────────────
    # Results
    # ──────────────────────────────────────────────────────────────────────

    def print_result(self, content: str, title: str = "Result") -> None:
        """Render the final result — Markdown if it looks like markdown, else plain panel."""
        highlighted = self._highlight_paths(content)
        if _looks_like_markdown(content):
            self.console.print(Panel(Markdown(content), title=f"[bold green]{title}[/bold green]", border_style="green"))
        else:
            self.console.print(Panel(highlighted, title=f"[bold green]{title}[/bold green]", border_style="green"))

    def print_file_written(self, path: str) -> None:
        """Highlight a successfully written output file."""
        self.console.print(f"\n[bold cyan]✅ Written:[/bold cyan] [bold]{path}[/bold]")

    # ──────────────────────────────────────────────────────────────────────
    # Interrupt / approval
    # ──────────────────────────────────────────────────────────────────────

    def print_interrupt_menu(self, step_number: int, total: int) -> str:
        """Show pause notice and prompt for interrupt action. Returns chosen option."""
        self.console.print(
            f"\n[bold red]⏸  Paused at Step {step_number}/{total}[/bold red]"
        )
        self.console.print("[dim][bold white]s[/bold white]kip[/dim] · [dim][bold white]r[/bold white]eplan[/dim] · [dim][bold white]c[/bold white]ontinue[/dim] · [dim][bold white]q[/bold white]uit[/dim]")
        raw_choice = Prompt.ask(
            "[bold]Choose action[/bold]",
            choices=["s", "r", "c", "q", "skip", "replan", "continue", "quit"],
            default="c",
            show_choices=False,
        ).lower()
        mapping = {
            "s": "skip", "skip": "skip",
            "r": "replan", "replan": "replan",
            "c": "continue", "continue": "continue",
            "q": "quit", "quit": "quit"
        }
        return mapping.get(raw_choice, "continue")

    def print_approval_prompt(self) -> str:
        """Prompt user to approve/edit/quit the plan. Returns 'approve'/'edit'/'quit'."""
        self.console.print()
        prompt_text = "[bold cyan]Approve plan?[/bold cyan] [dim]([bold white]A[/bold white]pprove / [bold white]E[/bold white]dit / [bold white]Q[/bold white]uit)[/dim]"
        raw_choice = Prompt.ask(
            prompt_text,
            choices=["a", "e", "q", "approve", "edit", "quit"],
            default="a",
            show_choices=False,
        ).lower()
        mapping = {
            "a": "approve", "approve": "approve",
            "e": "edit", "edit": "edit",
            "q": "quit", "quit": "quit"
        }
        return mapping.get(raw_choice, "approve")

    def print_intent_preview(self, summary: str, has_write_ops: bool) -> None:
        """Display intent summary panel before execution."""
        icon = "⚠️" if has_write_ops else "📋"
        write_note = "\n[dim yellow]⚠️  This task includes file write or script execution steps.[/dim yellow]" if has_write_ops else ""
        self.console.print(Panel(
            f"{escape(summary)}{write_note}",
            title=f"[bold cyan]{icon} What I'll Do[/bold cyan]",
            border_style="cyan",
            padding=(0, 1),
        ))

    def print_intent_approval(self, has_write_ops: bool) -> bool:
        """Prompt user to approve the intent. Returns True if approved."""
        if not has_write_ops:
            self.console.print("[dim]✓ Auto-approved (read-only task)[/dim]")
            return True
        self.console.print()
        raw = Prompt.ask(
            "[bold cyan]Proceed?[/bold cyan] [dim]([bold white]Y[/bold white]es / [bold white]N[/bold white]o)[/dim]",
            choices=["y", "n", "yes", "no"],
            default="y",
            show_choices=False,
        ).lower()
        return raw in ("y", "yes")

    def print_dynamic_step_header(self, iteration: int, max_iterations: int, reason: str = "") -> None:
        """Show iteration progress in the dynamic decision loop."""
        suffix = f"  [dim italic]{escape(reason[:80])}[/dim italic]" if reason else ""
        self.console.rule(f"[bold]Iteration {iteration}/{max_iterations}[/bold]{suffix}")

    def print_replan_prompt(self) -> str:
        """Prompt user for a re-plan instruction."""
        self.console.print()
        return Prompt.ask("[bold yellow]Re-plan instruction[/bold yellow]")

    def print_info(self, msg: str) -> None:
        self.console.print(f"[dim]{msg}[/dim]")

    def print_error(self, msg: str) -> None:
        self.console.print(f"[bold red]❌ {msg}[/bold red]")

    def print_step_header(self, step: PlanStep, total: int) -> None:
        self.console.rule(f"[bold]Step {step.step_number}/{total}: {step.description[:60]}[/bold]")

    # ──────────────────────────────────────────────────────────────────────
    # Skills table
    # ──────────────────────────────────────────────────────────────────────

    def print_skills_table(self, skills: dict) -> None:
        """Print all loaded skills."""
        if not skills:
            self.console.print("[dim]No skills loaded.[/dim]")
            return
        table = Table("Name", "Description", "File", box=box.SIMPLE, header_style="bold cyan")
        for name, skill in skills.items():
            table.add_row(name, skill.short_description, skill.file_path.name)
        self.console.print(table)

    # ──────────────────────────────────────────────────────────────────────
    # Helpers
    # ──────────────────────────────────────────────────────────────────────

    def _highlight_paths(self, text: str) -> str:
        """Bold cyan any file paths in the text."""
        return re.sub(r"((?:/[\w./\-_]+)+)", r"[bold cyan]\1[/bold cyan]", text)


def _looks_like_markdown(text: str) -> bool:
    """Heuristic: text contains markdown headings or list markers."""
    return bool(re.search(r"^#+\s|^\*\s|^-\s|^\d+\.\s|\*\*", text, re.MULTILINE))
