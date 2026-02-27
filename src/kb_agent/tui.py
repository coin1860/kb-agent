from textual.app import App, ComposeResult
from textual.widgets import Header, Input, RichLog, Button, Static, Label, TextArea
from textual.message import Message
from textual.containers import Container, Horizontal, Vertical, Grid
from textual.screen import ModalScreen
from textual.binding import Binding
from textual.events import Key
from textual import on, work
from textual.reactive import reactive
from datetime import datetime
from pathlib import Path
import os
import re
import subprocess
from rich.markdown import Markdown
from rich.padding import Padding

from kb_agent.engine import Engine
import kb_agent.config as config
from kb_agent.config import load_settings

# ─── Persistent Config ────────────────────────────────────────────────────────

ENV_FILE = Path.home() / ".kb_agent" / ".env"


def _save_env_file(api_key: str, base_url: str, model: str, data_folder: str = "", embedding_url: str = "", embedding_model: str = ""):
    ENV_FILE.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        f'KB_AGENT_LLM_API_KEY="{api_key}"',
        f'KB_AGENT_LLM_BASE_URL="{base_url}"',
        f'KB_AGENT_LLM_MODEL="{model}"',
    ]
    if data_folder:
        lines.append(f'KB_AGENT_DATA_FOLDER="{data_folder}"')
    if embedding_url:
        lines.append(f'KB_AGENT_EMBEDDING_URL="{embedding_url}"')
    if embedding_model:
        lines.append(f'KB_AGENT_EMBEDDING_MODEL="{embedding_model}"')
    if ENV_FILE.exists():
        for line in ENV_FILE.read_text(encoding="utf-8").splitlines():
            stripped = line.strip()
            if stripped and not stripped.startswith("#") and "=" in stripped:
                env_key, _, _ = stripped.partition("=")
                env_key = env_key.strip()
                if env_key not in ("KB_AGENT_LLM_API_KEY", "KB_AGENT_LLM_BASE_URL", "KB_AGENT_LLM_MODEL", "KB_AGENT_DATA_FOLDER", "KB_AGENT_EMBEDDING_URL", "KB_AGENT_EMBEDDING_MODEL"):
                    lines.append(stripped)
    ENV_FILE.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _save_env_var(key: str, value: str):
    """Save or update a single env var in the .env file."""
    ENV_FILE.parent.mkdir(parents=True, exist_ok=True)
    lines = []
    found = False
    if ENV_FILE.exists():
        for line in ENV_FILE.read_text(encoding="utf-8").splitlines():
            stripped = line.strip()
            if stripped and not stripped.startswith("#") and "=" in stripped:
                env_key, _, _ = stripped.partition("=")
                if env_key.strip() == key:
                    lines.append(f'{key}="{value}"')
                    found = True
                    continue
            lines.append(line)
    if not found:
        lines.append(f'{key}="{value}"')
    ENV_FILE.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _load_env_file():
    if ENV_FILE.exists():
        for line in ENV_FILE.read_text(encoding="utf-8").splitlines():
            stripped = line.strip()
            if stripped and not stripped.startswith("#") and "=" in stripped:
                key, _, value = stripped.partition("=")
                key = key.strip()
                value = value.strip().strip('"').strip("'")
                if key and key not in os.environ:
                    os.environ[key] = value


_load_env_file()

# ─── Slash Commands ──────────────────────────────────────────────────────────

SLASH_COMMANDS = [
    ("/clear", "Clear chat history"),
    ("/help", "Show available commands"),
    ("/quit", "Exit the application"),
    ("/settings", "Open settings dialog"),
    ("/web_engine", "Switch web engine (markdownify / crawl4ai)"),
]


# ─── Settings Modal ─────────────────────────────────────────────────────────

class SettingsScreen(ModalScreen[bool]):
    CSS = """
    SettingsScreen { align: center middle; }
    #settings-dialog {
        grid-size: 2;
        grid-gutter: 1 2;
        grid-rows: auto auto auto auto auto auto auto auto auto;
        padding: 1 2;
        width: 70;
        height: auto;
        max-height: 40;
        border: thick $primary 60%;
        background: $surface;
    }
    #settings-title {
        column-span: 2;
        text-align: center;
        text-style: bold;
        padding-bottom: 1;
    }
    .settings-label {
        height: 1;
        content-align: left middle;
        color: $text-muted;
    }
    .settings-input { width: 100%; }
    #settings-buttons {
        column-span: 2;
        height: 3;
        align: center middle;
    }
    #settings-buttons Button {
        margin: 0 1;
        min-width: 16;
    }
    """

    def compose(self) -> ComposeResult:
        current_url = str(config.settings.llm_base_url) if config.settings else ""
        current_model = config.settings.llm_model if config.settings else "gpt-4"
        current_data_folder = str(config.settings.data_folder) if config.settings and config.settings.data_folder else ""
        current_api_key = config.settings.llm_api_key.get_secret_value() if config.settings else ""
        current_embedding_url = config.settings.embedding_url if config.settings else ""
        current_embedding_model = config.settings.embedding_model if config.settings else ""

        with Grid(id="settings-dialog"):
            yield Label("⚙  Settings", id="settings-title")
            yield Label("API Key", classes="settings-label", id="lbl-api-key")
            yield Input(placeholder="sk-...", value=current_api_key, password=False, id="api_key", classes="settings-input")
            yield Label("Base URL", classes="settings-label", id="lbl-base-url")
            yield Input(
                placeholder="https://api.openai.com/v1",
                value=current_url or "https://api.openai.com/v1",
                id="base_url", classes="settings-input",
            )
            yield Label("Model", classes="settings-label", id="lbl-model")
            yield Input(placeholder="gpt-4", value=current_model, id="model_name", classes="settings-input")
            yield Label("Data Folder", classes="settings-label", id="lbl-data-folder")
            yield Input(
                placeholder="/path/to/data",
                value=current_data_folder,
                id="data_folder", classes="settings-input",
            )
            yield Label("Embedding URL", classes="settings-label", id="lbl-embedding-url")
            yield Input(
                placeholder="http://localhost:7999/v1",
                value=current_embedding_url,
                id="embedding_url", classes="settings-input",
            )
            yield Label("Embedding Model", classes="settings-label", id="lbl-embedding-model")
            yield Input(
                placeholder="all-MiniLM-L6-v2",
                value=current_embedding_model,
                id="embedding_model", classes="settings-input",
            )
            yield Label("Max Iterations", classes="settings-label", id="lbl-max-iter")
            yield Input(
                placeholder="1",
                value=os.getenv("KB_AGENT_MAX_ITERATIONS", "1"),
                id="max_iterations", classes="settings-input",
            )
            with Horizontal(id="settings-buttons"):
                yield Button("Save", id="save")
                yield Button("Cancel", id="cancel")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "save":
            api_key = self.query_one("#api_key").value.strip()
            base_url = self.query_one("#base_url").value.strip()
            model = self.query_one("#model_name").value.strip() or "gpt-4"
            data_folder = self.query_one("#data_folder").value.strip()
            embedding_url = self.query_one("#embedding_url").value.strip()
            embedding_model = self.query_one("#embedding_model").value.strip()

            if not api_key:
                self.notify("API Key is required!", severity="error")
                return
            if not base_url:
                self.notify("Base URL is required!", severity="error")
                return
            os.environ["KB_AGENT_LLM_API_KEY"] = api_key
            os.environ["KB_AGENT_LLM_BASE_URL"] = base_url
            os.environ["KB_AGENT_LLM_MODEL"] = model
            if data_folder:
                os.environ["KB_AGENT_DATA_FOLDER"] = data_folder
            elif "KB_AGENT_DATA_FOLDER" in os.environ:
                del os.environ["KB_AGENT_DATA_FOLDER"]

            if embedding_url:
                os.environ["KB_AGENT_EMBEDDING_URL"] = embedding_url
            elif "KB_AGENT_EMBEDDING_URL" in os.environ:
                del os.environ["KB_AGENT_EMBEDDING_URL"]

            if embedding_model:
                os.environ["KB_AGENT_EMBEDDING_MODEL"] = embedding_model
            elif "KB_AGENT_EMBEDDING_MODEL" in os.environ:
                del os.environ["KB_AGENT_EMBEDDING_MODEL"]

            # Max iterations (clamp 1-5)
            max_iter_raw = self.query_one("#max_iterations").value.strip() or "1"
            try:
                max_iter = max(1, min(5, int(max_iter_raw)))
            except ValueError:
                max_iter = 1
            os.environ["KB_AGENT_MAX_ITERATIONS"] = str(max_iter)
            _save_env_var("KB_AGENT_MAX_ITERATIONS", str(max_iter))

            _save_env_file(api_key, base_url, model, data_folder, embedding_url, embedding_model)
            if load_settings():
                self.dismiss(True)
            else:
                self.notify("Invalid settings.", severity="error")
        else:
            self.dismiss(False)


# ChatModeScreen removed.


# ─── Web Engine Selection Modal ──────────────────────────────────────────────

class WebEngineScreen(ModalScreen[str]):
    """Modal for choosing the web fetch engine."""

    selected_engine = reactive("markdownify")

    CSS = """
    WebEngineScreen { align: center middle; }
    #web-engine-dialog {
        padding: 1 2;
        width: 50;
        height: auto;
        border: thick $primary 60%;
        background: $surface;
    }
    #web-engine-title {
        text-align: center;
        text-style: bold;
        padding-bottom: 1;
    }
    .engine-option {
        width: 100%;
        padding: 1;
    }
    .engine-option:hover {
        background: $accent;
        color: auto;
    }
    .engine-option.active {
        color: $success;
        text-style: bold;
    }
    .engine-option.focused {
        background: $accent;
    }
    """

    def on_mount(self) -> None:
        self.selected_engine = os.getenv("KB_AGENT_WEB_ENGINE", "markdownify").lower()

    def compose(self) -> ComposeResult:
        with Vertical(id="web-engine-dialog"):
            yield Label("🌐  Web Engine", id="web-engine-title")
            
            md_lbl = Label(id="engine-markdownify", classes="engine-option")
            md_lbl.styles.content_align = ("left", "middle")
            yield md_lbl
            
            cr_lbl = Label(id="engine-crawl4ai", classes="engine-option")
            cr_lbl.styles.content_align = ("left", "middle")
            yield cr_lbl

    def watch_selected_engine(self, old_val: str, new_val: str) -> None:
        try:
            md_lbl = self.query_one("#engine-markdownify", Label)
            cr_lbl = self.query_one("#engine-crawl4ai", Label)
        except Exception:
            return

        current = os.getenv("KB_AGENT_WEB_ENGINE", "markdownify").lower()
        
        md_text = f"{'✅ ' if current == 'markdownify' else '   '}{'>> ' if new_val == 'markdownify' else '   '}markdownify (lightweight)"
        md_lbl.update(md_text)
        md_lbl.set_class(current == "markdownify", "active")
        md_lbl.set_class(new_val == "markdownify", "focused")
        
        cr_text = f"{'✅ ' if current == 'crawl4ai' else '   '}{'>> ' if new_val == 'crawl4ai' else '   '}crawl4ai (Playwright, JS)"
        cr_lbl.update(cr_text)
        cr_lbl.set_class(current == "crawl4ai", "active")
        cr_lbl.set_class(new_val == "crawl4ai", "focused")

    @on(Key)
    def handle_keys(self, event: Key) -> None:
        if event.key == "up":
            if self.selected_engine == "crawl4ai":
                self.selected_engine = "markdownify"
        elif event.key == "down":
            if self.selected_engine == "markdownify":
                self.selected_engine = "crawl4ai"
        elif event.key == "enter":
            self._save_and_dismiss(self.selected_engine)
        elif event.key == "escape":
            self.dismiss("")

    def on_click(self, event) -> None:
        widget = event.widget
        if widget and widget.id == "engine-markdownify":
            self._save_and_dismiss("markdownify")
        elif widget and widget.id == "engine-crawl4ai":
            self._save_and_dismiss("crawl4ai")
        else:
            self.dismiss("")

    def _save_and_dismiss(self, engine: str):
        if engine in ("markdownify", "crawl4ai"):
            os.environ["KB_AGENT_WEB_ENGINE"] = engine
            _save_env_var("KB_AGENT_WEB_ENGINE", engine)
            self.notify(f"Web engine set to: {engine}", severity="information")
            self.dismiss(engine)
        else:
            self.dismiss("")


# ─── Command Palette ─────────────────────────────────────────────────────────

class CommandPalette(Container):
    """Floating command list that appears above the input when / is typed."""

    DEFAULT_CSS = """
    CommandPalette {
        display: none;
        height: auto;
        max-height: 12;
        background: $surface;
        border: tall $accent;
        margin: 0 2;
        padding: 0;
    }
    CommandPalette.visible {
        display: block;
    }
    CommandPalette .cmd-row {
        height: 1;
        padding: 0 2;
    }
    CommandPalette .cmd-row.highlighted {
        background: $accent;
    }
    CommandPalette .cmd-name {
        width: 16;
        color: $text;
    }
    CommandPalette .cmd-desc {
        color: $text-muted;
    }
    """

    highlighted_index: reactive[int] = reactive(0)

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._filtered: list[tuple[str, str]] = []

    def filter_commands(self, text: str):
        prefix = text.lstrip("/").lower()
        self._filtered = [
            (cmd, desc) for cmd, desc in SLASH_COMMANDS
            if cmd[1:].startswith(prefix)
        ]
        self.highlighted_index = 0
        self._rebuild()
        if self._filtered:
            self.add_class("visible")
        else:
            self.remove_class("visible")

    def hide(self):
        self.remove_class("visible")
        self._filtered = []

    def _rebuild(self):
        self.remove_children()
        for i, (cmd, desc) in enumerate(self._filtered):
            row = Horizontal(classes="cmd-row")
            row.compose_add_child(Static(cmd, classes="cmd-name"))
            row.compose_add_child(Static(desc, classes="cmd-desc"))
            if i == self.highlighted_index:
                row.add_class("highlighted")
            self.mount(row)

    def watch_highlighted_index(self, value: int):
        rows = self.query(".cmd-row")
        for i, row in enumerate(rows):
            if i == value:
                row.add_class("highlighted")
            else:
                row.remove_class("highlighted")

    def move_up(self):
        if self._filtered:
            self.highlighted_index = (self.highlighted_index - 1) % len(self._filtered)

    def move_down(self):
        if self._filtered:
            self.highlighted_index = (self.highlighted_index + 1) % len(self._filtered)

    def get_selected(self) -> str | None:
        if self._filtered and 0 <= self.highlighted_index < len(self._filtered):
            return self._filtered[self.highlighted_index][0]
        return None

    @property
    def is_visible(self) -> bool:
        return self.has_class("visible")


# ─── Status Bar ──────────────────────────────────────────────────────────────

class StatusBar(Static):
    DEFAULT_CSS = """
    StatusBar {
        height: 1;
        color: $text-muted;
        padding: 0 2;
    }
    """

    def set_status(self, state: str, detail: str = "", mode: str = "knowledge_base"):
        indicators = {
            "idle": ("●", "green", "Ready"),
            "thinking": ("⟳", "yellow", "Working"),
            "error": ("✗", "red", "Error"),
            "disconnected": ("○", "red", "Not configured"),
        }
        emoji, color, label = indicators.get(state, ("?", "white", state))
        info = f" {detail}" if detail else ""
        
        mode_str = "Chat Mode" if mode == "normal" else "KB RAG Mode"
        mode_color = "green" if mode == "normal" else "#FFB000"
        
        model = ""
        if config.settings:
            model = f"  │  [{mode_color}]{mode_str}[/{mode_color}]  │  {config.settings.llm_model}"
        self.update(f" [{color}]{emoji}[/{color}] {label}{info}{model}")


# ─── Shortcut Hints ──────────────────────────────────────────────────────────

class ShortcutBar(Static):
    DEFAULT_CSS = """
    ShortcutBar {
        height: 1;
        text-align: center;
        color: $text-muted;
    }
    """

    def on_mount(self):
        self.update(
            "[bold]ctrl+s[/bold] settings  "
            "[bold]ctrl+l[/bold] clear  "
            "[bold]shift+enter[/bold] newline  "
            "[bold]tab[/bold] mode  "
            "[bold]ctrl+q[/bold] quit"
        )


# ─── Tip Bar ─────────────────────────────────────────────────────────────────

class TipBar(Static):
    DEFAULT_CSS = """
    TipBar {
        height: 1;
        padding: 0 2;
        color: $text-muted;
    }
    """

    def set_tip(self, text: str):
        self.update(f" [yellow]●[/yellow] [dim]Tip[/dim] {text}")


# ─── Constants ───────────────────────────────────────────────────────────────

LOGO = """\
[bold red]  ██████╗ ████████╗███████╗    ██╗  ██╗██████╗[/bold red]
[bold red] ██╔════╝ ╚══██╔══╝██╔════╝    ██║ ██╔╝██╔══██╗[/bold red]
[bold red] ██║  ███╗   ██║   ███████╗    █████╔╝ ██████╔╝[/bold red]
[bold red] ██║   ██║   ██║   ╚════██║    ██╔═██╗ ██╔══██╗[/bold red]
[bold red] ╚██████╔╝   ██║   ███████║    ██║  ██╗██████╔╝[/bold red]
[bold red]  ╚═════╝    ╚═╝   ╚══════╝    ╚═╝  ╚═╝╚═════╝[/bold red]
[bold red]      █████╗  ██████╗ ███████╗███╗   ██╗████████╗[/bold red]
[bold red]     ██╔══██╗██╔════╝ ██╔════╝████╗  ██║╚══██╔══╝[/bold red]
[bold red]     ███████║██║  ███╗█████╗  ██╔██╗ ██║   ██║[/bold red]
[bold red]     ██╔══██║██║   ██║██╔══╝  ██║╚██╗██║   ██║[/bold red]
[bold red]     ██║  ██║╚██████╔╝███████╗██║ ╚████║   ██║[/bold red]
[bold red]     ╚═╝  ╚═╝ ╚═════╝ ╚══════╝╚═╝  ╚═══╝   ╚═╝[/bold red]
"""

WELCOME = """\
[dim]Enterprise Knowledge Retrieval[/dim]
[dim]Hybrid search: grep + vector + knowledge graph + [bold]web scraping[/bold][/dim]

[dim]Author:[/dim]  [bold]Shane H SHOU[/bold]
[dim]GitHub:[/dim]  [link=https://github.com/coin1860/kb-agent]https://github.com/coin1860/kb-agent[/link]  ⭐ [italic]Star the repo if you find it useful![/italic]

[bold]ctrl+s[/bold] settings  [bold]ctrl+l[/bold] clear  [bold]ctrl+q[/bold] quit
[yellow]●[/yellow] [dim]Type[/dim] [bold yellow]/[/bold yellow] [dim]to see commands[/dim]  [dim]|[/dim]  [bold]Tab[/bold] [dim]switch mode[/dim]  [dim]|[/dim]  [dim]Paste[/dim] [bold]URL[/bold] [dim]to analyze[/dim]  [dim]|[/dim]  [bold]Enter[/bold] [dim]send,[/dim] [bold]Shift+Enter[/bold] [dim]newline[/dim]
[dim]────────────────────────────────────────[/dim]
"""

HELP_TEXT = """\
[bold cyan]Commands:[/bold cyan]
  [bold yellow]/help[/bold yellow]         Show this message
  [bold yellow]/settings[/bold yellow]     Configure API key, model & max iterations
  [bold yellow]/web_engine[/bold yellow]   Switch web engine (markdownify / crawl4ai)
  [bold yellow]/clear[/bold yellow]        Clear chat
  [bold yellow]/quit[/bold yellow]         Exit

[bold cyan]Shortcuts:[/bold cyan]
  [bold]Ctrl+Q[/bold] Quit   [bold]Ctrl+L[/bold] Clear   [bold]Ctrl+S[/bold] Settings

[bold cyan]Features:[/bold cyan]
  • Type a question to search the knowledge base
  • Paste a [bold]URL[/bold] to fetch & analyze web page content
  • Type [bold yellow]/[/bold yellow] for command autocomplete
  • [bold]Enter[/bold] to send, [bold]Shift+Enter[/bold] for new line
  • [bold]Tab[/bold] to toggle between RAG and Normal mode
[dim]────────────────────────────────────────[/dim]
"""


# ─── Chat Input (TextArea subclass) ────────────────────────────────────

class ChatInput(TextArea):
    """TextArea that sends Enter as submit, Shift+Enter as newline."""

    class Submitted(Message):
        """Posted when user presses Enter (without Shift)."""
        def __init__(self, text: str):
            super().__init__()
            self.text = text

    async def _on_key(self, event: Key) -> None:
        if event.key == "enter" and "shift" not in event.name:
            # Plain Enter = Submit
            event.prevent_default()
            event.stop()
            self.post_message(self.Submitted(self.text))
            return
        
        if event.key == "enter" and "shift" in event.name:
            # Shift+Enter = Newline
            self.insert("\n")
            event.prevent_default()
            event.stop()
            return

        # All other keys go to TextArea default
        await super()._on_key(event)


# ─── Main App ────────────────────────────────────────────────────────────────

class KBAgentApp(App):
    TITLE = "KB Agent"

    BINDINGS = [
        Binding("ctrl+q", "quit_app", "Quit", show=False, priority=True),
        Binding("ctrl+l", "clear_chat", "Clear", show=False),
        Binding("ctrl+s", "open_settings", "Settings", show=False),
        Binding("ctrl+a", "select_all_input", "Select All", show=False, priority=True),
    ]

    CSS = """
    Screen {
        layout: vertical;
    }

    /* ── Chat area ─────────────────────────────── */
    #chat-area {
        height: 1fr;
    }
    #chat-log {
        height: 100%;
        padding: 1 2;
        scrollbar-size: 1 1;
    }

    /* ── Bottom panel (palette + editor + bars) ── */
    #bottom-panel {
        height: auto;
        max-height: 24;
    }

    /* ── Editor box ────────────────────────────── */
    #editor-box {
        height: auto;
        min-height: 3;
        max-height: 10;
        border: tall $primary;
        margin: 0 2;
        padding: 0;
    }
    #chat-input {
        min-height: 1;
        max-height: 8;
        height: auto;
        border: none;
        padding: 0 1;
    }
    #chat-input:focus {
        border: none;
    }

    /* ── Info row (mode + model) ────────────────── */
    #info-row {
        height: 1;
        padding: 0 2;
        margin-top: 0;
    }
    #btn-copy {
        height: 1;
        min-width: 8;
        padding: 0 1;
        margin: 0 2;
        background: $accent;
        color: $text;
        border: none;
        display: none;
    }
    #btn-copy.visible {
        display: block;
    }
    """

    engine = None
    chat_mode: reactive[str] = reactive("knowledge_base")
    last_response: reactive[str] = reactive("")
    _suppress_palette = 0
    chat_history: list = []

    def on_mount(self) -> None:
        """Initialize per-instance state."""
        self.chat_history = []

    def compose(self) -> ComposeResult:
        model_name = config.settings.llm_model if config.settings else "not configured"
        yield Header(show_clock=False)

        # Chat messages area
        with Container(id="chat-area"):
            yield RichLog(id="chat-log", wrap=True, highlight=True, markup=True)

        # Bottom panel: palette + editor + status
        with Vertical(id="bottom-panel"):
            yield CommandPalette(id="cmd-palette")
            with Container(id="editor-box"):
                yield ChatInput(id="chat-input", language=None, show_line_numbers=False)
            yield Horizontal(
                StatusBar(id="status-bar"),
                Button("Copy", id="btn-copy"),
                id="info-row",
            )

    def watch_last_response(self, value: str):
        try:
            btn = self.query_one("#btn-copy")
            if value:
                btn.add_class("visible")
                if "```" in value:
                    btn.label = "Copy Code"
                else:
                    btn.label = "Copy"
            else:
                btn.remove_class("visible")
        except:
            pass

    @on(Button.Pressed, "#btn-copy")
    def on_copy_pressed(self):
        self.action_copy_last_response()

    def on_mount(self):
        log = self.query_one("#chat-log", RichLog)

        # Show logo + welcome on startup (no /help to keep it clean)
        log.write(LOGO)
        log.write(WELCOME)

        if config.settings:
            self.sub_title = config.settings.llm_model
        else:
            self.sub_title = "not configured"

        # Try init engine
        load_settings()
        if config.settings:
            try:
                self.engine = Engine()
                log.write("[green]● Engine ready[/green]")
            except Exception as e:
                log.write(f"[yellow]⚠ Engine init: {e}[/yellow]")
                log.write("[dim]Use /settings to configure[/dim]")
        else:
            self.set_timer(0.2, self._prompt_settings)

        self._refresh_status("idle")

        # Focus input
        ta = self.query_one("#chat-input", ChatInput)
        ta.focus()

    def _prompt_settings(self):
        self.push_screen(SettingsScreen(), self._on_settings_result)

    def _on_settings_result(self, result: bool):
        log = self.query_one("#chat-log", RichLog)
        if result:
            log.write("[green]● Settings saved[/green]")
            self.sub_title = config.settings.llm_model if config.settings else ""
            try:
                self.engine = Engine()
                log.write("[green]● Engine ready[/green]")
            except Exception as e:
                log.write(f"[red]✗ Engine init failed: {e}[/red]")
        else:
            log.write("[dim]Settings cancelled. Use /settings later.[/dim]")
        self._refresh_status("idle")
        self.query_one("#chat-input", ChatInput).focus()

    def _refresh_status(self, state: str, detail: str = ""):
        mode = getattr(self, "chat_mode", "knowledge_base")
        self.query_one("#status-bar", StatusBar).set_status(state, detail, mode)

    def _ts(self) -> str:
        return datetime.now().strftime("%H:%M:%S")

    # ─── Text changed → show palette ───────────────────────────────────────

    @on(TextArea.Changed, "#chat-input")
    def on_input_changed(self, event: TextArea.Changed):
        if self._suppress_palette > 0:
            self._suppress_palette -= 1
            return
        palette = self.query_one("#cmd-palette", CommandPalette)
        text = event.text_area.text.strip()
        if text.startswith("/") and len(text) >= 1 and "\n" not in text:
            palette.filter_commands(text)
        else:
            palette.hide()

    # ─── ChatInput.Submitted handler ───────────────────────────────────────

    @on(ChatInput.Submitted)
    def on_chat_submitted(self, event: ChatInput.Submitted):
        ta = self.query_one("#chat-input", ChatInput)
        palette = self.query_one("#cmd-palette", CommandPalette)

        # If palette is visible, handle selection
        if palette.is_visible:
            selected = palette.get_selected()
            palette.hide()
            if selected:
                if selected in ("/settings", "/web_engine", "/clear", "/quit"):
                    ta.clear()
                    self._suppress_palette = 2
                    self._exec_slash(selected)
                else:
                    self._suppress_palette = 2  # suppress clear() + insert() events
                    ta.clear()
                    ta.insert(selected + " ")
            return

        query = event.text.strip()
        ta.clear()
        self.last_response = ""

        if not query:
            return

        if query.startswith("/"):
            self._exec_slash(query)
            return

        # Normal query
        log = self.query_one("#chat-log", RichLog)
        log.write(f"\n  [dim]{self._ts()}[/dim]  [bold green]You[/bold green]")
        log.write(Padding(query, (0, 0, 0, 2)))

        if not self.engine:
            if config.settings is None:
                log.write("[yellow]⚠ Not configured[/yellow]")
                self.push_screen(SettingsScreen(), self._on_settings_result)
                return
            try:
                self.engine = Engine()
            except Exception as e:
                log.write(f"[red]✗ Engine init failed: {e}[/red]")
                return

        self._run_query(query)

    # ─── Key handling: palette navigation ───────────────────────────────

    def on_key(self, event: Key):
        palette = self.query_one("#cmd-palette", CommandPalette)
        
        if event.key == "tab":
            event.prevent_default()
            event.stop()
            if palette.is_visible:
                selected = palette.get_selected()
                if selected:
                    ta = self.query_one("#chat-input", ChatInput)
                    palette.hide()
                    if selected == "/settings":
                        ta.clear()
                        self._suppress_palette = 2
                        self._exec_slash(selected)
                    else:
                        ta.clear()
                        ta.insert(selected + " ")
            else:
                # Toggle chat mode
                self.chat_mode = "normal" if self.chat_mode == "knowledge_base" else "knowledge_base"
            return

        if not palette.is_visible:
            return

        if event.key == "up":
            palette.move_up()
            event.prevent_default()
            event.stop()
        elif event.key == "down":
            palette.move_down()
            event.prevent_default()
            event.stop()
        elif event.key == "escape":
            palette.hide()
            event.prevent_default()
            event.stop()

    def _exec_slash(self, cmd_text: str):
        cmd = cmd_text.lower().split()[0]
        log = self.query_one("#chat-log", RichLog)
        if cmd == "/help":
            log.write(HELP_TEXT)
        elif cmd == "/settings":
            self.action_open_settings()
        elif cmd == "/clear":
            self.action_clear_chat()
        elif cmd == "/web_engine":
            self.push_screen(WebEngineScreen())
        elif cmd == "/quit":
            self.exit()
        else:
            log.write(f"[red]Unknown command: {cmd}[/red]  [dim]Type /help[/dim]")

    # ─── Query Worker ─────────────────────────────────────────────────────

    @work(thread=True, exclusive=True)
    def _run_query(self, query: str):
        log = self.query_one("#chat-log", RichLog)

        def on_status(emoji, msg):
            self.call_from_thread(log.write, f"  [dim]{emoji} {msg}[/dim]")
            self.call_from_thread(self._refresh_status, "thinking", msg)

        self.call_from_thread(self._refresh_status, "thinking")
        self.call_from_thread(log.write, "")

        try:
            response = self.engine.answer_query(query, on_status=on_status, mode=self.chat_mode, history=self.chat_history)
            
            # Update history
            self.chat_history.append({"role": "user", "content": query})
            self.chat_history.append({"role": "assistant", "content": response})

            self.call_from_thread(log.write, "")
            self.call_from_thread(
                log.write,
                f"  [dim]{self._ts()}[/dim]  [bold blue]Agent[/bold blue]",
            )
            # Render the entire response as Markdown with indentation
            self.call_from_thread(log.write, Padding(Markdown(response), (0, 0, 0, 2)))
            
            # Set last response to enable Copy button
            self.last_response = response
            
            self.call_from_thread(
                log.write, "[dim]────────────────────────────────────────[/dim]"
            )
            self.call_from_thread(self._refresh_status, "idle")
        except Exception as e:
            self.call_from_thread(log.write, f"\n[red]✗ Error: {e}[/red]")
            self.call_from_thread(self._refresh_status, "error", str(e))

    # ─── Actions ──────────────────────────────────────────────────────────

    def action_quit_app(self):
        self.exit()

    def action_clear_chat(self):
        log = self.query_one("#chat-log", RichLog)
        log.clear()
        self.chat_history = []
        log.write("[dim]Chat history cleared.[/dim]")
        self.chat_history = []
        log.write("[dim]Chat history cleared.[/dim]")

    def action_open_settings(self):
        self.push_screen(SettingsScreen(), self._on_settings_result)

    def action_copy_last_response(self):
        if not self.last_response:
            return
        
        # Try to find code blocks
        code_blocks = re.findall(r'```(?:\w+)?\n(.*?)\n```', self.last_response, re.DOTALL)
        if code_blocks:
            # Join all code blocks
            text_to_copy = "\n\n".join(code_blocks)
            msg = "Code copied to clipboard!"
        else:
            text_to_copy = self.last_response
            msg = "Response copied to clipboard!"
        
        try:
            # Simple pbcopy for Mac
            subprocess.run(['pbcopy'], input=text_to_copy.encode('utf-8'), check=True)
            self.notify(msg)
        except Exception as e:
            self.notify(f"Copy failed: {e}", severity="error")

    def action_select_all_input(self):
        """Select all text in the TextArea input."""
        ta = self.query_one("#chat-input", TextArea)
        if ta.has_focus:
            ta.select_all()

    def action_open_chatmode(self):
        """Removed in favor of Tab switching."""
        pass

    def _on_chatmode_result(self, mode: str):
        if mode:
            self.chat_mode = mode

    def watch_chat_mode(self, mode: str):
        """Update UI when chat mode changes."""
        # Update border color of editor box
        try:
            box = self.query_one("#editor-box")
            if mode == "normal":
                box.styles.border = ("tall", "green")
                self.query_one("#chat-input").styles.cursor_color = "white"
            else:
                box.styles.border = ("tall", "darkorange")
                self.query_one("#chat-input").styles.cursor_color = "#FFB000"
            
            # Update status bar
            self._refresh_status("idle")
            
            # Log mode change
            log = self.query_one("#chat-log", RichLog)
            mode_name = "Chat Mode" if mode == "normal" else "KB RAG Mode"
            c = "green" if mode == "normal" else "#FFB000"
            log.write(f"\n[dim]{self._ts()}[/dim]  [{c}]● Switched to {mode_name}[/{c}]")
        except:
            pass
        
        ta = self.query_one("#chat-input", ChatInput)
        ta.focus()


def main():
    app = KBAgentApp()
    app.run()


if __name__ == "__main__":
    main()
