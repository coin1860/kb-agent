import asyncio
from textual.app import App
from textual.widgets import Markdown
from textual import work, on
from textual.message import Message

class TestApp(App):
    CSS = "Markdown { height: 1fr; width: 1fr; border: solid green; }"
    def compose(self):
        yield Markdown("__Start__", id="md")
        
    class AppendChat(Message):
        def __init__(self, text):
            super().__init__()
            self.text = text

    def on_mount(self):
        self.chat_history = "__Start__\n\n"
        self.do_stuff()
        self.post_message(self.AppendChat("From Mount! "))

    @on(AppendChat)
    async def _on_append_chat(self, event: AppendChat):
        self.chat_history += event.text
        md = self.query_one("#md", Markdown)
        await md.update(self.chat_history)

    @work(thread=True)
    def do_stuff(self):
        import time
        time.sleep(1)
        self.post_message(self.AppendChat("Hello "))
        time.sleep(1)
        self.post_message(self.AppendChat("World! "))
        time.sleep(1)
        self.call_from_thread(self.exit)

if __name__ == "__main__":
    app = TestApp()
    app.run()
