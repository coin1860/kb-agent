from textual.app import App, ComposeResult
from textual.widgets import Header, Footer, Input, Markdown, RichLog, Button, Static, Label
from textual.containers import Container, Horizontal, Vertical, Grid
from textual.screen import Screen, ModalScreen
from textual import on
import os
import asyncio

# Use explicit import for Engine to avoid circular dependency issues if any
from kb_agent.engine import Engine
import kb_agent.config as config
from kb_agent.config import load_settings
from kb_agent.audit import log_audit

class SettingsScreen(ModalScreen):
    CSS = """
    SettingsScreen {
        align: center middle;
    }
    #dialog {
        grid-size: 2;
        grid-gutter: 1 2;
        grid-rows: 1fr 1fr 3;
        padding: 1 2;
        width: 60;
        height: 14;
        border: thick $background 80%;
        background: $surface;
    }
    #question {
        column-span: 2;
        height: 1fr;
        width: 1fr;
        content-align: left middle;
    }
    Button {
        width: 100%;
    }
    """

    def compose(self) -> ComposeResult:
        with Grid(id="dialog"):
            yield Label("LLM API Key:", id="question")
            yield Input(placeholder="sk-...", password=True, id="api_key")
            yield Label("LLM Base URL:", id="question")
            yield Input(placeholder="https://api.openai.com/v1", value="https://api.openai.com/v1", id="base_url")
            yield Button("Save", variant="primary", id="save")
            yield Button("Cancel", variant="error", id="cancel")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "save":
            api_key = self.query_one("#api_key").value
            base_url = self.query_one("#base_url").value

            if api_key and base_url:
                os.environ["KB_AGENT_LLM_API_KEY"] = api_key
                os.environ["KB_AGENT_LLM_BASE_URL"] = base_url

                # Reload settings
                new_settings = load_settings()
                if new_settings:
                    self.dismiss(True)
                else:
                    self.notify("Settings invalid even after update. Check input.", severity="error")
            else:
                self.notify("Please enter API Key and Base URL", severity="error")
        else:
            self.dismiss(False)

class MainScreen(Screen):
    def compose(self) -> ComposeResult:
        yield Header()
        yield Container(
            Horizontal(
                Vertical(
                    Markdown(id="viewer"),
                    id="left-pane"
                ),
                Vertical(
                    RichLog(id="log", wrap=True, highlight=True, markup=True),
                    id="right-pane"
                )
            ),
            id="main-container"
        )
        yield Input(placeholder="Ask a question about internal docs...", id="input")
        yield Footer()

    async def on_input_submitted(self, event: Input.Submitted):
        query = event.value
        if not query.strip():
            return

        self.query_one("#input").value = ""
        log = self.query_one("#log")
        log.write(f"[bold green]User:[/bold green] {query}")

        # Check engine availability
        if not self.app.engine:
            if config.settings is None:
                self.notify("Configuration missing. Please set API Key.", severity="warning")
                await self.app.push_screen(SettingsScreen(), self.check_settings)
                # Re-submit query handled via check_settings? No, user has to type again or we store it.
                # For simplicity, user types again.
                return
            else:
                # Try to init if settings exist but engine not ready
                try:
                    self.app.engine = Engine()
                except Exception as e:
                    self.notify(f"Engine init failed: {e}", severity="error")
                    return

        self.run_worker(self.process_query(query))

    async def process_query(self, query: str):
        log = self.query_one("#log")
        viewer = self.query_one("#viewer")

        log.write("Thinking...")

        try:
            # Run blocking engine code in thread
            response = await asyncio.to_thread(self.app.engine.answer_query, query)
            viewer.update(response)
            log.write("[bold blue]Agent:[/bold blue] Done.")

        except Exception as e:
            log.write(f"[bold red]Error:[/bold red] {e}")
            viewer.update(f"Error: {e}")

    def check_settings(self, result: bool):
        if result:
            self.notify("Settings saved. Initializing Engine...")
            try:
                self.app.engine = Engine()
                self.notify("Engine ready.")
            except Exception as e:
                self.notify(f"Failed to init engine: {e}", severity="error")

class KBAgentApp(App):
    CSS = """
    Screen {
        layout: vertical;
    }
    #main-container {
        height: 1fr;
    }
    #left-pane {
        width: 70%;
        height: 100%;
        border-right: solid green;
    }
    #right-pane {
        width: 30%;
        height: 100%;
    }
    #viewer {
        padding: 1;
        height: 100%;
        overflow-y: scroll;
    }
    #log {
        height: 100%;
        overflow-y: scroll;
    }
    #input {
        dock: bottom;
    }
    """

    engine = None

    def on_mount(self):
        # Try to init engine
        if config.settings:
            try:
                self.engine = Engine()
            except Exception:
                pass

        if not self.engine:
            self.call_later(self.push_screen, SettingsScreen(), self.check_settings_app)

    def check_settings_app(self, result: bool):
        if result:
            try:
                self.engine = Engine()
                self.notify("Engine initialized.")
            except Exception as e:
                self.notify(f"Engine init failed: {e}", severity="error")
        else:
            # If user cancelled initial setup, we might exit or just show main screen without engine
            # self.exit()
            self.notify("Agent is not configured. Please use Settings.", severity="warning")

    def compose(self) -> ComposeResult:
        yield MainScreen()

def main():
    app = KBAgentApp()
    app.run()

if __name__ == "__main__":
    main()
