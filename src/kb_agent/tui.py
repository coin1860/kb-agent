from textual.app import App, ComposeResult
from textual.widgets import Header, Input, Markdown, Button, Static, Label, TextArea
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
import asyncio

from kb_agent.engine import Engine
import kb_agent.config as config
from kb_agent.config import load_settings

# ─── Persistent Config ────────────────────────────────────────────────────────

ENV_FILE = Path.home() / ".kb_agent" / ".env"


def _save_env_file(api_key: str, base_url: str, model: str):
    ENV_FILE.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        f'KB_AGENT_LLM_API_KEY="{api_key}"',
        f'KB_AGENT_LLM_BASE_URL="{base_url}"',
        f'KB_AGENT_LLM_MODEL="{model}"',
    ]
    if ENV_FILE.exists():
        for line in ENV_FILE.read_text(encoding="utf-8").splitlines():
            stripped = line.strip()
            if stripped and not stripped.startswith("#"):
                key = stripped.split("=", 1)[0]
                if key not in ("KB_AGENT_LLM_API_KEY", "KB_AGENT_LLM_BASE_URL", "KB_AGENT_LLM_MODEL"):
                    lines.append(stripped)
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
    ("/chatmode", "Select chat mode"),
    ("/clear", "Clear chat history"),
    ("/help", "Show available commands"),
    ("/quit", "Exit the application"),
    ("/settings", "Open settings dialog"),
]


# ─── Settings Modal ─────────────────────────────────────────────────────────

class SettingsScreen(ModalScreen[bool]):
    CSS = """
    SettingsScreen { align: center middle; }
    #settings-dialog {
        grid-size: 2;
        grid-gutter: 1 2;
        grid-rows: auto auto auto auto;
        padding: 1 2;
        width: 70;
        height: auto;
        max-height: 22;
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

        with Grid(id="settings-dialog"):
            yield Label("⚙  Settings", id="settings-title")
            yield Label("API Key", classes="settings-label", id="lbl-api-key")
            yield Input(placeholder="sk-...", password=True, id="api_key", classes="settings-input")
            yield Label("Base URL", classes="settings-label", id="lbl-base-url")
            yield Input(
                placeholder="https://api.openai.com/v1",
                value=current_url or "https://api.openai.com/v1",
                id="base_url", classes="settings-input",
            )
            yield Label("Model", classes="settings-label", id="lbl-model")
            yield Input(placeholder="gpt-4", value=current_model, id="model_name", classes="settings-input")
            with Horizontal(id="settings-buttons"):
                yield Button("Save", id="save")
                yield Button("Cancel", id="cancel")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "save":
            api_key = self.query_one("#api_key").value.strip()
            base_url = self.query_one("#base_url").value.strip()
            model = self.query_one("#model_name").value.strip() or "gpt-4"
            if not api_key:
                self.notify("API Key is required!", severity="error")
                return
            if not base_url:
                self.notify("Base URL is required!", severity="error")
                return
            os.environ["KB_AGENT_LLM_API_KEY"] = api_key
            os.environ["KB_AGENT_LLM_BASE_URL"] = base_url
            os.environ["KB_AGENT_LLM_MODEL"] = model
            _save_env_file(api_key, base_url, model)
            if load_settings():
                self.dismiss(True)
            else:
                self.notify("Invalid settings.", severity="error")
        else:
            self.dismiss(False)


class ChatModeScreen(ModalScreen[str]):
    BINDINGS = [
        Binding("up", "focus_previous", "Previous", show=False),
        Binding("down", "focus_next", "Next", show=False),
    ]

    CSS = """
    ChatModeScreen { align: center middle; }
    #chatmode-dialog {
        grid-size: 1;
        grid-gutter: 1 2;
        padding: 1 2;
        width: 44;
        height: auto;
        border: thick $primary 60%;
        background: $surface;
    }
    #chatmode-title {
        text-align: center;
        text-style: bold;
        padding-bottom: 1;
    }
    .chatmode-btn {
        width: 100%;
        margin-bottom: 1;
    }
    """

    def compose(self) -> ComposeResult:
        with Vertical(id="chatmode-dialog"):
            yield Label("💬 Select Chat Mode", id="chatmode-title")
            yield Button("Normal Mode", id="btn-normal", classes="chatmode-btn")
            yield Button("Knowledge Base Mode", id="btn-kb", classes="chatmode-btn")
            yield Button("Cancel", id="cancel", classes="chatmode-btn")

    def on_mount(self) -> None:
        self.query_one("#btn-normal").focus()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "btn-kb":
            self.dismiss("knowledge_base")
        elif event.button.id == "btn-normal":
            self.dismiss("normal")
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
        
        mode_str = "[Normal]" if mode == "normal" else "[KB Area]"
        model = ""
        if config.settings:
            model = f"  │  {mode_str}  │  {config.settings.llm_model}"
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
```
  ██████╗ ████████╗███████╗    ██╗  ██╗██████╗
 ██╔════╝ ╚══██╔══╝██╔════╝    ██║ ██╔╝██╔══██╗
 ██║  ███╗   ██║   ███████╗    █████╔╝ ██████╔╝
 ██║   ██║   ██║   ╚════██║    ██╔═██╗ ██╔══██╗
 ╚██████╔╝   ██║   ███████║    ██║  ██╗██████╔╝
  ╚═════╝    ╚═╝   ╚══════╝    ╚═╝  ╚═╝╚═════╝
      █████╗  ██████╗ ███████╗███╗   ██╗████████╗
     ██╔══██╗██╔════╝ ██╔════╝████╗  ██║╚══██╔══╝
     ███████║██║  ███╗█████╗  ██╔██╗ ██║   ██║
     ██╔══██║██║   ██║██╔══╝  ██║╚██╗██║   ██║
     ██║  ██║╚██████╔╝███████╗██║ ╚████║   ██║
     ╚═╝  ╚═╝ ╚═════╝ ╚══════╝╚═╝  ╚═══╝   ╚═╝
```
"""

WELCOME = """\
*Enterprise Knowledge Retrieval*\n
*Hybrid search: grep + vector + knowledge graph + **web scraping***\n

*Author:*  **Shane H SHOU**\n
*GitHub:*  [https://github.com/coin1860/kb-agent](https://github.com/coin1860/kb-agent)  ⭐ _Star the repo if you find it useful!_\n

**ctrl+s** settings  **ctrl+l** clear  **ctrl+q** quit\n
🟡 *Type* **/** *to see commands*  |  *Paste a* **URL** *to analyze web content*  |  **Enter** *send,* **Shift+Enter** *new line*
___
"""

HELP_TEXT = """\
**Commands:**
- **/help**       Show this message
- **/settings**   Configure API key & model
- **/clear**      Clear chat
- **/quit**       Exit

**Shortcuts:**
- **Ctrl+Q** Quit
- **Ctrl+L** Clear
- **Ctrl+S** Settings

**Features:**
- Type a question to search the knowledge base
- Paste a **URL** to fetch & analyze web page content
- Type **/** for command autocomplete
- **Enter** to send, **Shift+Enter** for new line
___
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
        if event.key == "enter":
            # Enter without shift = submit
            # NOTE: Do NOT clear here — the handler needs to check
            # palette state first (clearing triggers TextArea.Changed
            # which would hide the palette before handler runs).
            event.prevent_default()
            event.stop()
            self.post_message(self.Submitted(self.text))
            return
        # All other keys (including shift+enter) go to TextArea default
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
    """

    engine = None
    chat_mode: reactive[str] = reactive("knowledge_base")
    chat_history: str = ""
    _suppress_palette = 0

    def compose(self) -> ComposeResult:
        model_name = config.settings.llm_model if config.settings else "not configured"
        yield Header(show_clock=False)

        # Chat messages area
        with Container(id="chat-area"):
            yield Markdown(id="chat-log")

        # Bottom panel: palette + editor + status
        with Vertical(id="bottom-panel"):
            yield CommandPalette(id="cmd-palette")
            with Container(id="editor-box"):
                yield ChatInput(id="chat-input", language=None, show_line_numbers=False)
            yield Horizontal(
                StatusBar(id="status-bar"),
                id="info-row",
            )

    async def on_mount(self):
        log = self.query_one("#chat-log", Markdown)

        # Show logo + welcome on startup (no /help to keep it clean)
        self.chat_history = LOGO + "\n\n" + WELCOME + "\n\n"
        await log.update(self.chat_history)

        if config.settings:
            self.sub_title = config.settings.llm_model
        else:
            self.sub_title = "not configured"

        # Try init engine
        load_settings()
        if config.settings:
            try:
                self.engine = Engine()
                self._append_to_chat("🟢 **Engine ready**\n\n")
            except Exception as e:
                self._append_to_chat(f"⚠️ **Engine init: {e}**\n\n_Use /settings to configure_")
        else:
            self.set_timer(0.2, self._prompt_settings)

        self._refresh_status("idle")

        # Focus input
        ta = self.query_one("#chat-input", ChatInput)
        ta.focus()

    class AppendChat(Message):
        def __init__(self, text: str):
            super().__init__()
            self.text = text

    def _append_to_chat(self, text: str):
        # post_message is thread-safe in Textual
        self.post_message(self.AppendChat(text))

    @on(AppendChat)
    async def _on_append_chat(self, event: AppendChat):
        self.chat_history += event.text
        log = self.query_one("#chat-log", Markdown)
        await log.update(self.chat_history)
        
        container = self.query_one("#chat-area", Container)
        container.scroll_end(animate=False)

    def _prompt_settings(self):
        self.push_screen(SettingsScreen(), self._on_settings_result)

    def _on_settings_result(self, result: bool):
        if result:
            self._append_to_chat("🟢 **Settings saved**\n\n")
            self.sub_title = config.settings.llm_model if config.settings else ""
            try:
                self.engine = Engine()
                self._append_to_chat("🟢 **Engine ready**\n\n")
            except Exception as e:
                self._append_to_chat(f"❌ **Engine init failed:** {e}\n\n")
        else:
            self._append_to_chat("_Settings cancelled. Use /settings later._\n\n")
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
                if selected in ("/settings", "/chatmode"):
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

        if not query:
            return

        if query.startswith("/"):
            self._exec_slash(query)
            return

        # Normal query
        self._append_to_chat(f"*{self._ts()}*  **👤 You**  \n{query}\n\n")

        if not self.engine:
            if config.settings is None:
                self._append_to_chat("⚠️ **Not configured**\n\n")
                self.push_screen(SettingsScreen(), self._on_settings_result)
                return
            try:
                self.engine = Engine()
            except Exception as e:
                self._append_to_chat(f"❌ **Engine init failed:** {e}\n\n")
                return

        self._run_query(query)

    # ─── Key handling: palette navigation ───────────────────────────────

    def on_key(self, event: Key):
        palette = self.query_one("#cmd-palette", CommandPalette)
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
        elif event.key == "tab":
            selected = palette.get_selected()
            if selected:
                ta = self.query_one("#chat-input", ChatInput)
                palette.hide()
                if selected in ("/settings", "/chatmode"):
                    ta.clear()
                    self._suppress_palette = 2
                    self._exec_slash(selected)
                else:
                    ta.clear()
                    ta.insert(selected + " ")
            event.prevent_default()
            event.stop()

    def _exec_slash(self, cmd_text: str):
        cmd = cmd_text.lower().split()[0]
        if cmd == "/help":
            self._append_to_chat(HELP_TEXT + "\n\n")
        elif cmd == "/chatmode":
            self.action_open_chatmode()
        elif cmd == "/settings":
            self.action_open_settings()
        elif cmd == "/clear":
            self.action_clear_chat()
        elif cmd == "/quit":
            self.exit()
        else:
            self._append_to_chat(f"❌ **Unknown command:** {cmd}  *Type /help*\n\n")

    # ─── Query Worker ─────────────────────────────────────────────────────

    @work(thread=True, exclusive=True)
    def _run_query(self, query: str):
        def on_status(emoji, msg):
            # This is a bit tricky with full markdown updates.
            # We can append it, but we might get status clutter.
            # Let's just update the status bar for now to avoid chat history clutter.
            self.call_from_thread(self._refresh_status, "thinking", msg)

        self.call_from_thread(self._refresh_status, "thinking")

        try:
            response = self.engine.answer_query(query, on_status=on_status, mode=self.chat_mode)
            self._append_to_chat(f"*{self._ts()}*  **🤖 Agent**\n\n{response}\n\n___\n\n")
            self.call_from_thread(self._refresh_status, "idle")
        except Exception as e:
            self._append_to_chat(f"❌ **Error:** {e}\n\n")
            self.call_from_thread(self._refresh_status, "error", str(e))

    # ─── Actions ──────────────────────────────────────────────────────────

    def action_quit_app(self):
        self.exit()

    def action_clear_chat(self):
        self.chat_history = ""
        self.post_message(self.AppendChat(""))

    def action_open_settings(self):
        self.push_screen(SettingsScreen(), self._on_settings_result)

    def action_select_all_input(self):
        """Select all text in the TextArea input."""
        ta = self.query_one("#chat-input", TextArea)
        if ta.has_focus:
            ta.select_all()

    def action_open_chatmode(self):
        self.push_screen(ChatModeScreen(), self._on_chatmode_result)

    def _on_chatmode_result(self, mode: str):
        if mode:
            self.chat_mode = mode
            mode_name = "Normal Mode" if mode == "normal" else "Knowledge Base Mode"
            self._append_to_chat(f"*{self._ts()}*  🟢 **Switched to {mode_name}**\n\n")
            self._refresh_status("idle")
        
        ta = self.query_one("#chat-input", ChatInput)
        ta.focus()


def main():
    app = KBAgentApp()
    app.run()


if __name__ == "__main__":
    main()
