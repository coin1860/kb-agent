import asyncio
from textual.app import App
from textual.widgets import Markdown
from textual import work, on
from textual.message import Message
import sys

class AppendChat(Message):
    def __init__(self, text):
        super().__init__()
        self.text = text

class TestApp(App):
    def compose(self):
        yield Markdown("__Start__", id="md")
        
    def on_mount(self):
        self.chat_history = "__Start__\n\n"
        self.do_stuff()

    @on(AppendChat)
    async def _on_append_chat(self, event: AppendChat):
        # Let's print to a file to be absolutely sure this runs
        with open("test_message_out.txt", "a") as f:
            f.write(f"RECEIVED: {event.text}\n")
        self.chat_history += event.text
        md = self.query_one("#md", Markdown)
        await md.update(self.chat_history)

    @work(thread=True)
    def do_stuff(self):
        import time
        time.sleep(1)
        self.post_message(AppendChat("Hello "))
        time.sleep(1)
        self.post_message(AppendChat("World! "))
        time.sleep(1)
        self.call_from_thread(self.exit)

if __name__ == "__main__":
    with open("test_message_out.txt", "w") as f:
         f.write("START\n")
    app = TestApp()
    app.run()
    print("DONE RUNNING")
