from textual.app import ComposeResult
from textual.containers import Container, Horizontal, Vertical
from textual.widgets import RichLog, Static, Input, ListView, ListItem, Label
from textual.reactive import reactive
from textual.message import Message

class AgentPlanPanel(Static):
    """Displays the current plan outline with status icons."""
    
    PLAN_ICONS = {
        "pending": "⬜",
        "active": "🔄",
        "completed": "✅",
        "failed": "❌",
        "skipped": "⏭"
    }

    def compose(self) -> ComposeResult:
        with Vertical():
            yield Label("📋 [bold]Current Plan[/bold]", id="agent-plan-header")
            yield RichLog(id="agent-plan-log", wrap=True, markup=True)

    def update_plan(self, plan: list[dict]):
        log = self.query_one("#agent-plan-log", RichLog)
        log.clear()
        if not plan:
            log.write("[dim]Empty plan.[/dim]")
            return

        for i, step in enumerate(plan):
            status = step.get("status", "pending")
            icon = self.PLAN_ICONS.get(status, "⬜")
            desc = step.get("description", "Untitled step")
            
            # Highlight current step if possible
            if status == "active":
                log.write(f"{i+1}. [bold cyan]{icon} {desc}[/bold cyan]")
            else:
                log.write(f"{i+1}. {icon} {desc}")

class AgentExecutionLog(Static):
    """Displays the continuous execution logs for the active session."""
    
    def compose(self) -> ComposeResult:
        with Vertical():
            yield Label("🎬 Execution Log", id="agent-exec-header")
            yield RichLog(id="agent-exec-log", wrap=True, markup=True)

class AgentModeView(Container):
    """The main view for the Agent Mode tab."""
    
    CSS = """
    AgentModeView {
        layout: vertical;
        height: 100%;
        width: 100%;
    }
    #agent-split {
        layout: horizontal;
        height: 1fr;
    }
    AgentExecutionLog {
        width: 2fr;
        height: 100%;
        border-right: solid cyan;
        padding: 1;
    }
    AgentPlanPanel {
        width: 1fr;
        height: 100%;
        padding: 1;
    }
    #agent-plan-header, #agent-exec-header {
        text-style: bold;
        padding-bottom: 1;
        color: cyan;
    }
    """
    
    def compose(self) -> ComposeResult:
        with Horizontal(id="agent-split"):
            yield AgentExecutionLog()
            yield AgentPlanPanel()
