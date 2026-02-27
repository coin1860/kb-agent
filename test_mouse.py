from textual.app import App, ComposeResult
from textual.widgets import Label

class TestApp(App):
    def compose(self) -> ComposeResult:
        yield Label("This is a test label. Try selecting me with the mouse.")

if __name__ == "__main__":
    app = TestApp()
    app.run(mouse=False)
