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
import concurrent.futures
from rich.markdown import Markdown
from rich.padding import Padding

from kb_agent.engine import Engine
from kb_agent.config import load_settings
from kb_agent import config
from kb_agent.tools.reranker import reranker_client

# ─── Slash Commands ──────────────────────────────────────────────────────────

SLASH_COMMANDS = [
    ("/clear", "Clear chat history"),
    ("/file_search", "Search files in the knowledge base"),
    ("/help", "Show available commands"),
    ("/index", "Index a URL, Jira ticket, or Confluence page"),
    ("/quit", "Exit the application"),
    ("/settings", "Open settings dialog"),
    ("/sync_confluence", "Sync Confluence page tree"),
    ("/web_engine", "Switch web engine (markdownify / crawl4ai)"),
]


# ─── Settings Modal ─────────────────────────────────────────────────────────

# ─── Settings Category Definitions ──────────────────────────────────────────

SETTINGS_CATEGORIES = [
    ("llm", "🤖  LLM", "API Key, Base URL, Model, Embeddings"),
    ("rag", "🔍  RAG", "Iterations, Score Threshold, Chunking"),
    ("atlassian", "🔗  Atlassian", "Jira & Confluence URLs and Tokens"),
    ("general", "⚙️   General", "Data Folder, Debug Mode"),
]


class SettingsCategoryScreen(ModalScreen[bool]):
    """Level 1: Category selection menu for settings."""

    BINDINGS = [
        Binding("escape", "cancel", "Close", show=False),
    ]

    CSS = """
    SettingsCategoryScreen { align: center middle; }
    #settings-dialog {
        padding: 1 2;
        width: 50;
        height: auto;
        border: thick darkorange 60%;
        background: $surface;
    }
    #settings-title {
        text-align: center;
        text-style: bold;
        padding-bottom: 1;
    }
    .cat-row {
        width: 100%;
        height: 3;
        padding: 0 2;
        content-align: left middle;
    }
    .cat-row:hover {
        background: $accent;
    }
    .cat-row.highlighted {
        background: $accent;
    }
    """

    highlighted_index: reactive[int] = reactive(0)
    _saved_any: bool = False

    def compose(self) -> ComposeResult:
        with Vertical(id="settings-dialog"):
            yield Label("⚙  Settings", id="settings-title")
            for i, (key, title, desc) in enumerate(SETTINGS_CATEGORIES):
                lbl = Label(f"  {title}\n  [dim]{desc}[/dim]", id=f"cat-{key}", classes="cat-row")
                yield lbl

    def on_mount(self) -> None:
        self._update_highlight()

    def watch_highlighted_index(self, old_val: int, new_val: int) -> None:
        self._update_highlight()

    def _update_highlight(self) -> None:
        rows = self.query(".cat-row")
        for i, row in enumerate(rows):
            if i == self.highlighted_index:
                row.add_class("highlighted")
            else:
                row.remove_class("highlighted")

    @on(Key)
    def handle_keys(self, event: Key) -> None:
        if event.key == "up":
            self.highlighted_index = (self.highlighted_index - 1) % len(SETTINGS_CATEGORIES)
            event.prevent_default()
            event.stop()
        elif event.key == "down":
            self.highlighted_index = (self.highlighted_index + 1) % len(SETTINGS_CATEGORIES)
            event.prevent_default()
            event.stop()
        elif event.key == "enter":
            self._open_detail()
            event.prevent_default()
            event.stop()

    def on_click(self, event) -> None:
        widget = event.widget
        if widget and hasattr(widget, 'id') and widget.id and widget.id.startswith("cat-"):
            cat_key = widget.id[4:]
            for i, (key, _, _) in enumerate(SETTINGS_CATEGORIES):
                if key == cat_key:
                    self.highlighted_index = i
                    self._open_detail()
                    return

    def _open_detail(self) -> None:
        cat_key = SETTINGS_CATEGORIES[self.highlighted_index][0]
        self.app.push_screen(
            SettingsDetailScreen(cat_key),
            self._on_detail_result,
        )

    def _on_detail_result(self, saved: bool) -> None:
        if saved:
            self._saved_any = True

    def action_cancel(self) -> None:
        self.dismiss(self._saved_any)


class SettingsDetailScreen(ModalScreen[bool]):
    """Level 2: Detail form for a single settings category."""

    BINDINGS = [
        Binding("escape", "go_back", "Back", show=False),
    ]

    CSS = """
    SettingsDetailScreen { align: center middle; }
    #detail-dialog {
        grid-size: 2;
        grid-gutter: 1 2;
        grid-rows: auto;
        padding: 1 2;
        width: 70;
        height: auto;
        max-height: 80vh;
        overflow-y: auto;
        border: thick darkorange 60%;
        background: $surface;
    }
    #detail-title {
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
    #detail-buttons {
        column-span: 2;
        height: 3;
        align: center middle;
    }
    #detail-buttons Button {
        margin: 0 1;
        min-width: 16;
    }
    """

    def __init__(self, category: str, **kwargs):
        super().__init__(**kwargs)
        self.category = category

    def compose(self) -> ComposeResult:
        cat_title = next((t for k, t, _ in SETTINGS_CATEGORIES if k == self.category), "Settings")

        with Grid(id="detail-dialog"):
            yield Label(f"{cat_title}", id="detail-title")

            if self.category == "llm":
                yield from self._compose_llm()
            elif self.category == "rag":
                yield from self._compose_rag()
            elif self.category == "atlassian":
                yield from self._compose_atlassian()
            elif self.category == "general":
                yield from self._compose_general()

            with Horizontal(id="detail-buttons"):
                yield Button("Save", id="save")
                yield Button("Back", id="cancel")

    # ── Field composers per category ──────────────────────────────────

    def _compose_llm(self):
        s = config.settings
        api_key = s.llm_api_key.get_secret_value() if s and s.llm_api_key else ""
        base_url = str(s.llm_base_url) if s and s.llm_base_url else ""
        model = s.llm_model if s and s.llm_model else "gpt-4"
        emb_url = s.embedding_url if s and s.embedding_url else ""
        emb_model = s.embedding_model if s and s.embedding_model else ""
        emb_model_path = str(s.embedding_model_path) if s and s.embedding_model_path else ""

        yield Label("API Key", classes="settings-label", id="lbl-api-key")
        yield Input(placeholder="sk-...", value=api_key, password=False, id="api_key", classes="settings-input")
        yield Label("Base URL", classes="settings-label", id="lbl-base-url")
        yield Input(placeholder="https://api.openai.com/v1", value=base_url or "https://api.openai.com/v1", id="base_url", classes="settings-input")
        yield Label("Model", classes="settings-label", id="lbl-model")
        yield Input(placeholder="gpt-4", value=model, id="model_name", classes="settings-input")
        yield Label("Embedding URL", classes="settings-label", id="lbl-embedding-url")
        yield Input(placeholder="http://localhost:7999/v1", value=emb_url, id="embedding_url", classes="settings-input")
        yield Label("Embedding Model", classes="settings-label", id="lbl-embedding-model")
        yield Input(placeholder="all-MiniLM-L6-v2", value=emb_model, id="embedding_model", classes="settings-input")
        yield Label("Local Model Path", classes="settings-label", id="lbl-embedding-model-path")
        yield Input(placeholder="/path/to/local/models", value=emb_model_path, id="embedding_model_path", classes="settings-input")

    def _compose_rag(self):
        s = config.settings
        max_iter = str(s.max_iterations) if s and s.max_iterations is not None else "1"
        threshold = str(s.vector_score_threshold) if s and s.vector_score_threshold is not None else "0.5"
        chunk_max = str(s.chunk_max_chars) if s and s.chunk_max_chars is not None else "800"
        chunk_overlap = str(s.chunk_overlap_chars) if s and s.chunk_overlap_chars is not None else "200"
        use_reranker = str(s.use_reranker) if s and s.use_reranker is not None else "False"
        reranker_path = str(s.reranker_model_path) if s and s.reranker_model_path else ""

        yield Label("Max Iterations", classes="settings-label", id="lbl-max-iter")
        yield Input(placeholder="1", value=max_iter, id="max_iterations", classes="settings-input")
        yield Label("Vector Score Threshold", classes="settings-label", id="lbl-vector-threshold")
        yield Input(placeholder="0.5", value=threshold, id="vector_score_threshold", classes="settings-input")
        yield Label("Chunk Max Chars", classes="settings-label", id="lbl-chunk-max")
        yield Input(placeholder="800", value=chunk_max, id="chunk_max_chars", classes="settings-input")
        yield Label("Chunk Overlap Chars", classes="settings-label", id="lbl-chunk-overlap")
        yield Input(placeholder="200", value=chunk_overlap, id="chunk_overlap_chars", classes="settings-input")
        yield Label("Use Cross-Encoder Reranker", classes="settings-label", id="lbl-use-reranker")
        yield Input(placeholder="True / False", value=use_reranker, id="use_reranker", classes="settings-input")
        yield Label("Reranker Model Path", classes="settings-label", id="lbl-reranker-path")
        yield Input(placeholder="models/bge-reranker-v2-m3-Q4_K_M.gguf", value=reranker_path, id="reranker_model_path", classes="settings-input")

    def _compose_atlassian(self):
        s = config.settings
        jira_url = str(s.jira_url) if s and s.jira_url else ""
        jira_token = s.jira_token.get_secret_value() if s and s.jira_token else ""
        conf_url = str(s.confluence_url) if s and s.confluence_url else ""
        conf_token = s.confluence_token.get_secret_value() if s and s.confluence_token else ""

        yield Label("Jira URL", classes="settings-label", id="lbl-jira-url")
        yield Input(placeholder="https://jira.company.com", value=jira_url, id="jira_url", classes="settings-input")
        yield Label("Jira Token (PAT)", classes="settings-label", id="lbl-jira-token")
        yield Input(placeholder="...", value=jira_token, password=True, id="jira_token", classes="settings-input")
        yield Label("Confluence URL", classes="settings-label", id="lbl-confluence-url")
        yield Input(placeholder="https://confluence.company.com", value=conf_url, id="confluence_url", classes="settings-input")
        yield Label("Confluence Token (PAT)", classes="settings-label", id="lbl-confluence-token")
        yield Input(placeholder="...", value=conf_token, password=True, id="confluence_token", classes="settings-input")

    def _compose_general(self):
        s = config.settings
        data_folder = str(s.data_folder) if s and s.data_folder else ""
        debug_mode = str(s.debug_mode) if s and s.debug_mode is not None else "False"

        yield Label("Data Folder", classes="settings-label", id="lbl-data-folder")
        yield Input(placeholder="/path/to/data", value=data_folder, id="data_folder", classes="settings-input")
        yield Label("Debug Mode", classes="settings-label", id="lbl-debug-mode")
        yield Input(placeholder="True / False", value=debug_mode, id="debug_mode", classes="settings-input")

    # ── Save logic ────────────────────────────────────────────────────

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "save":
            self._save()
        else:
            self.dismiss(False)

    def action_go_back(self) -> None:
        self.dismiss(False)

    def _save(self) -> None:
        """Collect fields from the current category, merge with existing settings, and persist."""
        updates = {}

        if self.category == "llm":
            api_key = self.query_one("#api_key").value.strip()
            base_url = self.query_one("#base_url").value.strip()
            model = self.query_one("#model_name").value.strip() or "gpt-4"
            emb_url = self.query_one("#embedding_url").value.strip()
            emb_model = self.query_one("#embedding_model").value.strip()
            emb_model_path = self.query_one("#embedding_model_path").value.strip()
            if not api_key:
                # Accept empty API key if base_url is a local endpoint
                if "localhost" not in base_url and "127.0.0.1" not in base_url:
                    self.notify("API Key is required for remote models!", severity="error")
                    return
                # Otherwise, it's local, we use a placeholder or None.
            if not base_url:
                self.notify("Base URL is required!", severity="error")
                return
            updates = {
                "llm_api_key": api_key,
                "llm_base_url": base_url,
                "llm_model": model,
                "embedding_url": emb_url or None,
                "embedding_model": emb_model or None,
                "embedding_model_path": emb_model_path or None,
            }

        elif self.category == "rag":
            max_iter_raw = self.query_one("#max_iterations").value.strip() or "1"
            threshold_raw = self.query_one("#vector_score_threshold").value.strip() or "0.5"
            chunk_max_raw = self.query_one("#chunk_max_chars").value.strip() or "800"
            chunk_overlap_raw = self.query_one("#chunk_overlap_chars").value.strip() or "200"
            use_reranker_raw = self.query_one("#use_reranker").value.strip().lower()
            use_reranker = use_reranker_raw in ("true", "1", "yes", "t", "y")
            reranker_path = self.query_one("#reranker_model_path").value.strip()
            try:
                max_iter = max(1, min(5, int(max_iter_raw)))
            except ValueError:
                max_iter = 1
            try:
                threshold = float(threshold_raw)
            except ValueError:
                threshold = 0.5
            try:
                chunk_max = int(chunk_max_raw)
            except ValueError:
                chunk_max = 800
            try:
                chunk_overlap = int(chunk_overlap_raw)
            except ValueError:
                chunk_overlap = 200
            updates = {
                "max_iterations": max_iter,
                "vector_score_threshold": threshold,
                "chunk_max_chars": chunk_max,
                "chunk_overlap_chars": chunk_overlap,
                "use_reranker": use_reranker,
                "reranker_model_path": reranker_path or None,
            }
            os.environ["KB_AGENT_MAX_ITERATIONS"] = str(max_iter)

            was_reranker_enabled = config.settings.use_reranker if config.settings else False
            if use_reranker and not was_reranker_enabled:
                self.notify("Reranker enabled. Please restart kb-agent to load the model.", severity="warning", timeout=6.0)

        elif self.category == "atlassian":
            jira_url = self.query_one("#jira_url").value.strip()
            jira_token = self.query_one("#jira_token").value.strip()
            conf_url = self.query_one("#confluence_url").value.strip()
            conf_token = self.query_one("#confluence_token").value.strip()
            updates = {
                "jira_url": jira_url or None,
                "jira_token": jira_token or None,
                "confluence_url": conf_url or None,
                "confluence_token": conf_token or None,
            }

        elif self.category == "general":
            data_folder = self.query_one("#data_folder").value.strip()
            debug_mode_raw = self.query_one("#debug_mode").value.strip().lower()
            debug_mode = debug_mode_raw in ("true", "1", "yes", "t", "y")
            updates = {
                "data_folder": data_folder or None,
                "debug_mode": debug_mode,
            }

        # Merge with existing settings
        new_settings_data = {}
        if config.settings:
            from pydantic import SecretStr
            new_settings_data = config.settings.model_dump(mode='json')
            # model_dump masks SecretStr as '**********'; unpack to real values
            for field_name, value in config.settings:
                if isinstance(value, SecretStr):
                    new_settings_data[field_name] = value.get_secret_value()
        new_settings_data.update(updates)

        try:
            new_settings = config.Settings(**new_settings_data)
            config.save_settings(new_settings)
            if config.load_settings():
                self.notify("Settings saved.", severity="information")
                self.dismiss(True)
            else:
                self.notify("Invalid settings.", severity="error")
        except Exception as e:
            err_msg = "Validation Error"
            if hasattr(e, 'errors'):
                errs = [str(err.get('loc', [''])[0]) for err in e.errors() if 'loc' in err]
                if errs:
                    err_msg = f"Invalid format for: {', '.join(errs)}"
            self.notify(err_msg, severity="error")


# Backward-compatible alias so existing references & tests keep working
SettingsScreen = SettingsCategoryScreen


class ConfluenceSyncScreen(ModalScreen[dict]):
    """Modal for configuring Confluence sync."""

    CSS = """
    ConfluenceSyncScreen { align: center middle; }
    #sync-dialog {
        grid-size: 2;
        grid-gutter: 1 2;
        grid-rows: auto auto auto auto;
        padding: 1 2;
        width: 50;
        height: auto;
        border: thick darkorange 60%;
        background: $surface;
    }
    #sync-title {
        column-span: 2;
        text-align: center;
        text-style: bold;
        padding-bottom: 1;
    }
    .sync-label { height: 1; content-align: left middle; color: $text-muted; }
    .sync-input { width: 100%; }
    #sync-buttons {
        column-span: 2;
        height: 3;
        align: center middle;
    }
    #sync-buttons Button { margin: 0 1; min-width: 16; }
    """

    def compose(self) -> ComposeResult:
        with Grid(id="sync-dialog"):
            yield Label("Sync Confluence Tree", id="sync-title")
            yield Label("Root Page ID", classes="sync-label")
            yield Input(placeholder="e.g. 12345678", id="root_page_id", classes="sync-input")
            yield Label("Crawl Depth (1-3)", classes="sync-label")
            yield Input(value="3", id="crawl_depth", classes="sync-input")
            with Horizontal(id="sync-buttons"):
                yield Button("Start Sync", id="start")
                yield Button("Cancel", id="cancel")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "start":
            page_id = self.query_one("#root_page_id").value.strip()
            depth_str = self.query_one("#crawl_depth").value.strip()
            if not page_id:
                self.notify("Page ID is required", severity="error")
                return
            try:
                depth = int(depth_str)
                if depth < 1 or depth > 3:
                    raise ValueError()
            except ValueError:
                self.notify("Depth must be between 1 and 3", severity="error")
                return
            self.dismiss({"page_id": page_id, "depth": depth})
        else:
            self.dismiss(None)


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
            config.update_setting("web_engine", engine)
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
        width: 20;
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
  [bold yellow]/help[/bold yellow]          Show this message
  [bold yellow]/settings[/bold yellow]      Configure API key, model & max iterations
  [bold yellow]/web_engine[/bold yellow]    Switch web engine (markdownify / crawl4ai)
  [bold yellow]/file_search[/bold yellow]   Search files in the knowledge base
  [bold yellow]/clear[/bold yellow]         Clear chat
  [bold yellow]/quit[/bold yellow]          Exit

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
        Binding("C", "clear_chat", "Clear", show=False),
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
        dock: right;
        margin: 1 2;
        display: none;
        layer: overlay;
        background: transparent;
        color: $text-muted;
        min-width: 8;
        height: 1;
        border: none;
    }
    #btn-copy:hover {
        background: $boost;
        color: $text;
    }
    #source-links-container {
        height: auto;
        min-height: 0;
        max-height: 4;
        padding: 0 2 1 2;
        display: none;
    }
    #source-links-container.visible {
        display: block;
    }
    .source-label {
        height: 1;
        padding: 0 1 0 0;
    }
    .source-link-btn {
        margin-right: 1;
        margin-bottom: 1;
        height: 1;
        border: none;
        background: $panel;
        min-width: 10;
        padding: 0 1;
    }
    .source-link-btn:hover {
        background: $primary;
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
            yield Button("📋 Copy", id="btn-copy")

        # Bottom panel: palette + editor + status
        with Vertical(id="bottom-panel"):
            yield CommandPalette(id="cmd-palette")
            with Container(id="editor-box"):
                yield ChatInput(id="chat-input", language=None, show_line_numbers=False)
            yield Horizontal(
                StatusBar(id="status-bar"),
                id="info-row",
            )

    def watch_last_response(self, value: str):
        try:
            btn = self.query_one("#btn-copy")
            if value:
                btn.display = True
            else:
                btn.display = False
        except:
            pass

    @on(Button.Pressed, "#btn-copy")
    def on_copy_pressed(self):
        self.action_copy_last_response()

    async def on_mount(self):
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
                await reranker_client.initialize()
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
                if selected in ("/settings", "/web_engine", "/clear", "/quit", "/sync_confluence", "/help"):
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
                    if selected in ("/settings", "/web_engine", "/clear", "/quit", "/sync_confluence", "/help"):
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
        parts = cmd_text.strip().split(maxsplit=1)
        cmd = parts[0].lower()
        log = self.query_one("#chat-log", RichLog)
        
        if cmd == "/help":
            log.write(HELP_TEXT)
        elif cmd == "/settings":
            self.action_open_settings()
        elif cmd == "/clear":
            self.action_clear_chat()
        elif cmd == "/web_engine":
            self.push_screen(WebEngineScreen())
        elif cmd == "/file_search":
            if len(parts) < 2:
                log.write("[yellow]Usage: /file_search <query>[/yellow]")
            else:
                self._run_file_search(parts[1])
        elif cmd == "/index":
            if len(parts) < 2:
                log.write("[yellow]Usage: /index <url | jira_id | confluence_id>[/yellow]")
            else:
                self._run_index_command(parts[1])
        elif cmd == "/sync_confluence":
            self.push_screen(ConfluenceSyncScreen(), self._run_confluence_sync)
        elif cmd == "/quit":
            self.exit()
        else:
            log.write(f"[red]Unknown command: {cmd}[/red]  [dim]Type /help[/dim]")

    def _run_confluence_sync(self, result: dict | None):
        if result:
            self._run_confluence_sync_worker(result["page_id"], result["depth"])

    @work(thread=True, exclusive=True)
    def _run_confluence_sync_worker(self, page_id: str, depth: int):
        log = self.query_one("#chat-log", RichLog)

        self.call_from_thread(self._refresh_status, "thinking", f"Syncing Confluence (Page {page_id}, Depth {depth})...")
        self.call_from_thread(log.write, "")
        self.call_from_thread(log.write, f"  [dim]{self._ts()}[/dim]  [bold blue]System[/bold blue]")
        self.call_from_thread(log.write, f"  [dim]Starting Confluence sync for Root ID {page_id} up to depth {depth}...[/dim]")

        from kb_agent.connectors.confluence import ConfluenceConnector
        import re

        try:
            connector = ConfluenceConnector()

            def progress_cb(count, title):
                self.call_from_thread(log.write, f"  [dim]✓ [{count}] Fetched & Saved: {title}[/dim]")

            output_dir = Path(config.settings.data_folder) / "source" / "confluence" if config.settings and config.settings.data_folder else Path("source/confluence")
            output_dir.mkdir(parents=True, exist_ok=True)

            saved_count = 0
            for page in connector.crawl_tree(page_id, max_depth=depth, on_progress=progress_cb):
                space = page["metadata"].get("space", "UNKNOWN")
                p_id = page["id"]
                title = page["title"]
                safe_title = re.sub(r'[^\w\-]', '_', title)
                filename = f"{space}_{p_id}_{safe_title}.md"

                filepath = output_dir / filename
                with open(filepath, "w", encoding="utf-8") as f:
                    f.write(page["content"])
                saved_count += 1

            msg = f"✓ Sync complete! Saved {saved_count} pages to `source/confluence/`\n\nRun `/index` or `kb-agent index` to update the search index."
            self.call_from_thread(log.write, Padding(Markdown(msg), (0, 0, 0, 2)))

        except Exception as e:
            self.call_from_thread(log.write, f"\n[red]✗ Sync failed: {e}[/red]")
        finally:
            self.call_from_thread(self._refresh_status, "idle")

    # ─── Query Worker ─────────────────────────────────────────────────────

    @work(thread=True, exclusive=True)
    def _run_index_command(self, target: str):
        """Asynchronously trigger the engine's index_resource command."""
        log = self.query_one("#chat-log", RichLog)

        def on_status(emoji, msg):
            self.call_from_thread(log.write, f"  [dim]{emoji} {msg}[/dim]")

        self.call_from_thread(self._refresh_status, "thinking", "Indexing...")
        self.call_from_thread(log.write, "")
        self.call_from_thread(log.write, f"  [dim]{self._ts()}[/dim]  [bold blue]System[/bold blue]")
        
        try:
            # engine.index_resource will handle routing to Web/Jira/Confluence 
            # and writing progress iteratively using on_status
            result = self.engine.index_resource(target, on_status=on_status)
            
            # Write final output (which might be success or failure string from engine)
            self.call_from_thread(log.write, "")
            self.call_from_thread(log.write, Padding(result, (0, 0, 0, 2)))
        except Exception as e:
            self.call_from_thread(log.write, f"\n[red]✗ Error indexing {target}: {e}[/red]")
        finally:
            self.call_from_thread(log.write, "[dim]────────────────────────────────────────[/dim]")
            self.call_from_thread(self._refresh_status, "idle")

    @work(thread=True, exclusive=True)
    def _run_file_search(self, query: str):
        """Search files via parallel ChromaDB queries with hardcoded sub-query decomposition."""
        log = self.query_one("#chat-log", RichLog)

        self.call_from_thread(self._refresh_status, "thinking", "Searching files...")
        self.call_from_thread(log.write, "")
        self.call_from_thread(
            log.write,
            f"  [dim]{self._ts()}[/dim]  [bold green]You[/bold green]",
        )
        self.call_from_thread(log.write, Padding(f"/file_search {query}", (0, 0, 0, 2)))
        self.call_from_thread(log.write, "")
        self.call_from_thread(
            log.write,
            f"  [dim]{self._ts()}[/dim]  [bold blue]System[/bold blue]",
        )

        try:
            from kb_agent.tools.vector_tool import VectorTool

            # 1. Hardcoded sub-query decomposition
            sub_queries = [
                query,
                f"关于 {query} 的相关内容",
                f"{query} 文档 资料 说明",
            ]
            self.call_from_thread(log.write, f"  [dim]🔀 Decomposed into {len(sub_queries)} sub-queries[/dim]")

            # 2. Parallel ChromaDB search
            vt = VectorTool()

            def _search(q: str):
                return vt.search(q, n_results=10)

            all_chunks = []
            with concurrent.futures.ThreadPoolExecutor(max_workers=3) as pool:
                futures = {pool.submit(_search, sq): sq for sq in sub_queries}
                for fut in concurrent.futures.as_completed(futures):
                    sq = futures[fut]
                    try:
                        results = fut.result()
                        all_chunks.extend(results)
                        self.call_from_thread(
                            log.write,
                            f"  [dim]🔍 Sub-query '{sq[:40]}' → {len(results)} chunks[/dim]",
                        )
                    except Exception as e:
                        self.call_from_thread(
                            log.write,
                            f"  [dim]❌ Sub-query '{sq[:40]}' failed: {e}[/dim]",
                        )

            # 3. Distinct chunks by id
            seen_ids = set()
            unique_chunks = []
            for c in all_chunks:
                cid = c.get("id", "")
                if cid and cid not in seen_ids:
                    seen_ids.add(cid)
                    unique_chunks.append(c)

            self.call_from_thread(
                log.write,
                f"  [dim]🧹 Deduplicated: {len(all_chunks)} → {len(unique_chunks)} chunks[/dim]",
            )

            # 4. Sort by score ascending (L2 distance, lower = more relevant)
            unique_chunks.sort(key=lambda x: x.get("score", float("inf")))

            # 5. Extract unique files, top 5
            seen_files = set()
            top_files = []
            for c in unique_chunks:
                meta = c.get("metadata", {})
                # Use metadata.get("path") if available (which points to source file like file.pdf)
                original_path = meta.get("path")
                if not original_path:
                    raw_path = meta.get("file_path") or meta.get("related_file") or ""
                    if not raw_path:
                        continue
                    # Normalize: source/X.pdf → index/X.md just to have something safe
                    original_path = self._normalize_file_path(raw_path)
                
                # Fetch original filename and derive index link
                import urllib.parse
                fname = os.path.basename(original_path)
                stem = os.path.splitext(fname)[0]
                
                # After indexing, files live in index_path as .md
                index_file_path = str(config.settings.index_path.absolute() / f"{stem}.md")
                
                # Use standard 'file://' prefix with URL encoding to pass to terminal
                encoded_path = urllib.parse.quote(index_file_path)
                index_link = f"file://{encoded_path}"

                if fname in seen_files:
                    continue
                seen_files.add(fname)

                score = c.get("score", float("inf"))
                desc = c.get("content", "")[:80].replace("|", " ").replace("\n", " ").strip()
                top_files.append((fname, index_link, score, desc))
                if len(top_files) >= 5:
                    break

            # 6. Render as a rich.table.Table to support terminal hyperlinks
            if top_files:
                from rich.table import Table
                table = Table(show_header=True, expand=True)
                table.add_column("Index", justify="right", style="cyan", no_wrap=True)
                table.add_column("Filename", style="green", no_wrap=True)
                table.add_column("Score", style="magenta", no_wrap=True)
                table.add_column("Desc", style="white")

                for i, (fname, link, score, desc) in enumerate(top_files, 1):
                    formatted_score = f"{score:.3f}" if score != float("inf") else "N/A"
                    # Use rich markup for the hyperlink
                    table.add_row(str(i), f"[link={link}]{fname}[/link]", formatted_score, desc)
                
                self.call_from_thread(log.write, Padding(table, (0, 0, 0, 2)))
            else:
                self.call_from_thread(
                    log.write,
                    "  [yellow]No matching files found in the knowledge base.[/yellow]",
                )

        except Exception as e:
            self.call_from_thread(log.write, f"\n[red]✗ File search error: {e}[/red]")
        finally:
            self.call_from_thread(
                log.write, "[dim]────────────────────────────────────────[/dim]"
            )
            self.call_from_thread(self._refresh_status, "idle")

    @staticmethod
    def _normalize_file_path(path: str) -> str:
        """Normalize source/X.pdf → index/X.md"""
        if not path:
            return path
        # Replace source/ directory prefix with index/
        path = re.sub(r'(^|[/\\])source([/\\])', r'\1index\2', path)
        # Replace known binary extensions with .md
        base, ext = os.path.splitext(path)
        if ext.lower() in ('.pdf', '.docx', '.xlsx', '.csv', '.txt'):
            path = base + '.md'
        return path

    @work(thread=True, exclusive=True)
    def _run_query(self, query: str):
        log = self.query_one("#chat-log", RichLog)

        def on_status(emoji, msg):
            self.call_from_thread(log.write, f"  [dim]{emoji} {msg}[/dim]")
            self.call_from_thread(self._refresh_status, "thinking", msg)

        self.call_from_thread(self._refresh_status, "thinking")
        self.call_from_thread(log.write, "")

        try:
            response_tuple = self.engine.answer_query(query, on_status=on_status, mode=self.chat_mode, history=self.chat_history)
            
            if isinstance(response_tuple, tuple) and len(response_tuple) == 2:
                response, sources = response_tuple
            else:
                response = str(response_tuple)
                sources = []
            
            # Save sources for the modal action links
            self._current_sources = sources
            
            # Update history (strictly WITHOUT sources)
            self.chat_history.append({"role": "user", "content": query})
            self.chat_history.append({"role": "assistant", "content": response})

            self.call_from_thread(log.write, "")
            self.call_from_thread(
                log.write,
                f"  [dim]{self._ts()}[/dim]  [bold blue]Agent[/bold blue]",
            )
            # Render the entire response as Markdown with indentation
            self.call_from_thread(log.write, Padding(Markdown(response), (0, 0, 0, 2)))
            
            # Write sources as static text to the RichLog
            if sources:
                self.call_from_thread(log.write, "  [bold italic]🔗 Sources:[/bold italic]")
                for src in sources:
                    path = src.get('path', 'Unknown')
                    filename = path.split('/')[-1] if '/' in path else path
                    line = src.get('line', '1')
                    score = src.get('score')
                    
                    if score is not None:
                        sim = max(1, min(99, int((1.0 - (score / 2.0)) * 100)))
                        score_text = f" ({sim}%)"
                    else:
                        score_text = ""
                        
                    self.call_from_thread(log.write, f"    [dim]📄 {filename} (Line {line}){score_text}[/dim]")
            
            
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
        self.last_response = ""
        try:
            self.query_one("#btn-copy").display = False
        except:
            pass
            
        try:
            import kb_agent.tools.csv_qa_tool as csv_tool
            csv_tool.clear_cache()
        except ImportError:
            pass
            
        log.write("[dim]Chat history cleared.[/dim]")

    def action_open_settings(self):
        self.push_screen(SettingsScreen(), self._on_settings_result)

    def action_copy_last_response(self):
        if not self.last_response:
            return
        
        md_text = self.last_response
        
        try:
            # Direct copy as plain text (Markdown)
            subprocess.run(['pbcopy'], input=md_text.encode('utf-8'), check=True)
            self.notify("Response copied as Markdown to clipboard!")
            return
            
            
            

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
