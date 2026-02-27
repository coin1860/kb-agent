"""
Automated TUI tests for kb-agent.
Run: python -m pytest tests/test_tui.py -v
"""
import os
import sys
import pytest
from unittest.mock import patch, MagicMock
from pathlib import Path

os.environ["KB_AGENT_LLM_API_KEY"] = "test-key-12345"
os.environ["KB_AGENT_LLM_BASE_URL"] = "http://localhost:8080"
os.environ["KB_AGENT_LLM_MODEL"] = "test-model"

# Mock audit before it opens audit.log
_mock_audit = MagicMock()
_mock_audit.log_audit = MagicMock()
_mock_audit.log_search = MagicMock()
_mock_audit.log_llm_response = MagicMock()
_mock_audit.log_tool_use = MagicMock()
sys.modules["kb_agent.audit"] = _mock_audit

# Mock heavy deps
for mod in ["chromadb", "chromadb.config", "chromadb.utils",
            "chromadb.utils.embedding_functions", "sentence_transformers", "ripgrep"]:
    if mod not in sys.modules:
        sys.modules[mod] = MagicMock()

from kb_agent.tui import (
    KBAgentApp, CommandPalette, StatusBar, ChatInput,
    SettingsScreen, SLASH_COMMANDS, LOGO, WELCOME, HELP_TEXT,
)
from textual.widgets import Markdown, Input, Header, TextArea


def make_app():
    with patch("kb_agent.tui.Engine"):
        return KBAgentApp()


# ─── App Startup ─────────────────────────────────────────────────────────────

class TestAppStartup:
    async def test_app_composes(self):
        app = make_app()
        async with app.run_test():
            assert app.is_running

    async def test_all_core_widgets_exist(self):
        app = make_app()
        async with app.run_test():
            assert app.query_one("#chat-log", Markdown) is not None
            assert app.query_one("#chat-input", ChatInput) is not None
            assert app.query_one("#cmd-palette", CommandPalette) is not None
            assert app.query_one("#status-bar", StatusBar) is not None

    async def test_editor_box_exists(self):
        app = make_app()
        async with app.run_test():
            assert app.query_one("#editor-box") is not None

    async def test_palette_hidden_initially(self):
        app = make_app()
        async with app.run_test():
            p = app.query_one("#cmd-palette", CommandPalette)
            assert not p.has_class("visible")

    async def test_input_is_chat_input(self):
        """Chat input should be a ChatInput (TextArea subclass)."""
        app = make_app()
        async with app.run_test():
            ta = app.query_one("#chat-input", ChatInput)
            assert isinstance(ta, TextArea)

    async def test_input_focused_on_start(self):
        app = make_app()
        async with app.run_test():
            ta = app.query_one("#chat-input", ChatInput)
            assert ta.has_focus


# ─── Logo and Welcome ────────────────────────────────────────────────────────

class TestWelcome:
    def test_logo_not_empty(self):
        assert len(LOGO) > 50

    def test_logo_has_markdown_block(self):
        assert "```" in LOGO

    def test_welcome_has_author(self):
        assert "Shane H SHOU" in WELCOME

    def test_welcome_has_github(self):
        assert "github.com/coin1860/kb-agent" in WELCOME

    def test_welcome_has_shortcuts(self):
        assert "ctrl+s" in WELCOME
        assert "ctrl+l" in WELCOME
        assert "ctrl+q" in WELCOME

    def test_welcome_has_tips(self):
        assert "URL" in WELCOME
        assert "Shift+Enter" in WELCOME

    def test_help_has_feature_url(self):
        assert "URL" in HELP_TEXT


# ─── ChatInput Enter behavior ───────────────────────────────────────────────

class TestChatInput:
    async def test_enter_submits_text(self):
        """Enter should submit and text should be processed."""
        app = make_app()
        async with app.run_test() as pilot:
            ta = app.query_one("#chat-input", ChatInput)
            # Typing /help triggers palette, so first enter fills command
            ta.insert("/help")
            await pilot.pause()
            await pilot.press("enter")  # first enter: palette fills command
            await pilot.pause()
            await pilot.press("enter")  # second enter: executes command
            await pilot.pause()
            assert ta.text == ""

    async def test_enter_with_normal_text(self):
        """Normal text (no palette) should submit on first enter."""
        app = make_app()
        async with app.run_test() as pilot:
            mock_engine = MagicMock()
            mock_engine.answer_query.return_value = "ok"
            app.engine = mock_engine
            ta = app.query_one("#chat-input", ChatInput)
            ta.insert("hello world")
            await pilot.pause()
            await pilot.press("enter")
            await pilot.pause(delay=0.5)
            assert ta.text == ""

    async def test_palette_enter_fills_command(self):
        """When palette visible, enter fills command into input (unless it's /settings or /chatmode)."""
        app = make_app()
        async with app.run_test() as pilot:
            ta = app.query_one("#chat-input", ChatInput)
            p = app.query_one("#cmd-palette", CommandPalette)
            ta.insert("/help")
            await pilot.pause()
            assert p.has_class("visible")
            await pilot.press("enter")  # fills selected command
            await pilot.pause()
            # Command should be filled into input (not executed yet) for /help
            text = ta.text.strip()
            assert text.startswith("/help")


# ─── Command Palette ─────────────────────────────────────────────────────────

class TestCommandPalette:
    async def test_filter_all(self):
        app = make_app()
        async with app.run_test():
            p = app.query_one("#cmd-palette", CommandPalette)
            p.filter_commands("/")
            assert len(p._filtered) == len(SLASH_COMMANDS)
            assert p.has_class("visible")

    async def test_filter_help(self):
        app = make_app()
        async with app.run_test():
            p = app.query_one("#cmd-palette", CommandPalette)
            p.filter_commands("/he")
            assert len(p._filtered) == 1
            assert p._filtered[0][0] == "/help"

    async def test_filter_settings(self):
        app = make_app()
        async with app.run_test():
            p = app.query_one("#cmd-palette", CommandPalette)
            p.filter_commands("/se")
            assert len(p._filtered) == 1
            assert p._filtered[0][0] == "/settings"

    async def test_filter_no_match(self):
        app = make_app()
        async with app.run_test():
            p = app.query_one("#cmd-palette", CommandPalette)
            p.filter_commands("/zzz")
            assert len(p._filtered) == 0
            assert not p.has_class("visible")

    async def test_navigation_down(self):
        app = make_app()
        async with app.run_test():
            p = app.query_one("#cmd-palette", CommandPalette)
            p.filter_commands("/")
            assert p.highlighted_index == 0
            p.move_down()
            assert p.highlighted_index == 1

    async def test_navigation_up_wraps(self):
        app = make_app()
        async with app.run_test():
            p = app.query_one("#cmd-palette", CommandPalette)
            p.filter_commands("/")
            p.move_up()
            assert p.highlighted_index == len(SLASH_COMMANDS) - 1

    async def test_navigation_wrap_full(self):
        app = make_app()
        async with app.run_test():
            p = app.query_one("#cmd-palette", CommandPalette)
            p.filter_commands("/")
            for _ in range(len(SLASH_COMMANDS)):
                p.move_down()
            assert p.highlighted_index == 0

    async def test_get_selected(self):
        app = make_app()
        async with app.run_test():
            p = app.query_one("#cmd-palette", CommandPalette)
            p.filter_commands("/")
            assert p.get_selected() == SLASH_COMMANDS[0][0]
            p.move_down()
            assert p.get_selected() == SLASH_COMMANDS[1][0]

    async def test_hide(self):
        app = make_app()
        async with app.run_test():
            p = app.query_one("#cmd-palette", CommandPalette)
            p.filter_commands("/")
            assert p.has_class("visible")
            p.hide()
            assert not p.has_class("visible")
            assert len(p._filtered) == 0


# ─── Slash Commands ──────────────────────────────────────────────────────────

class TestSlashCommands:
    async def test_help_executes(self):
        """Slash commands execute properly (palette fill → enter to run)."""
        app = make_app()
        async with app.run_test() as pilot:
            ta = app.query_one("#chat-input", ChatInput)
            ta.insert("/help")
            await pilot.pause()
            # First enter fills from palette, second executes
            await pilot.press("enter")
            await pilot.pause()
            await pilot.press("enter")
            await pilot.pause()
            assert ta.text == ""

    async def test_clear_executes(self):
        app = make_app()
        async with app.run_test() as pilot:
            ta = app.query_one("#chat-input", ChatInput)
            ta.insert("/clear")
            await pilot.pause()
            await pilot.press("enter")
            await pilot.pause()
            await pilot.press("enter")
            await pilot.pause()
            assert ta.text == ""

    async def test_unknown(self):
        app = make_app()
        async with app.run_test() as pilot:
            ta = app.query_one("#chat-input", ChatInput)
            ta.insert("/foobar")
            await pilot.pause()
            await pilot.press("enter")
            await pilot.pause()
            # /foobar doesn't match any command, no palette fill
            assert ta.text == ""

    async def test_empty_noop(self):
        app = make_app()
        async with app.run_test() as pilot:
            ta = app.query_one("#chat-input", ChatInput)
            await pilot.press("enter")
            await pilot.pause()


# ─── Status Bar ──────────────────────────────────────────────────────────────

class TestStatusBar:
    async def test_idle(self):
        app = make_app()
        async with app.run_test():
            app.query_one("#status-bar", StatusBar).set_status("idle")

    async def test_thinking(self):
        app = make_app()
        async with app.run_test():
            app.query_one("#status-bar", StatusBar).set_status("thinking", "Searching...")

    async def test_error(self):
        app = make_app()
        async with app.run_test():
            app.query_one("#status-bar", StatusBar).set_status("error", "Timeout")

    async def test_disconnected(self):
        app = make_app()
        async with app.run_test():
            app.query_one("#status-bar", StatusBar).set_status("disconnected")


# ─── Settings Modal ──────────────────────────────────────────────────────────

class TestSettings:
    async def test_composes(self):
        app = make_app()
        async with app.run_test() as pilot:
            app.push_screen(SettingsScreen(), app._on_settings_result)
            await pilot.pause(delay=0.5)
            assert app.screen.query_one("#settings-dialog") is not None

    async def test_all_inputs(self):
        app = make_app()
        async with app.run_test() as pilot:
            app.push_screen(SettingsScreen(), app._on_settings_result)
            await pilot.pause(delay=0.5)
            assert app.screen.query_one("#api_key", Input) is not None
            assert app.screen.query_one("#base_url", Input) is not None
            assert app.screen.query_one("#model_name", Input) is not None

    async def test_cancel(self):
        app = make_app()
        async with app.run_test() as pilot:
            app.push_screen(SettingsScreen(), app._on_settings_result)
            await pilot.pause(delay=0.5)
            await pilot.click("#cancel")
            await pilot.pause()


# ─── Chat Mode Modal ──────────────────────────────────────────────────────────

class TestChatMode:
    async def test_composes(self):
        from kb_agent.tui import ChatModeScreen
        from kb_agent import config
        app = make_app()
        config.settings = MagicMock()
        async with app.run_test() as pilot:
            app.push_screen(ChatModeScreen(), app._on_chatmode_result)
            await pilot.pause(delay=0.5)
            # Find the screen explicitly
            chat_screen = next(s for s in app.screen_stack if isinstance(s, ChatModeScreen))
            assert chat_screen.query_one("#chatmode-dialog") is not None

    async def test_all_buttons(self):
        from kb_agent.tui import ChatModeScreen
        from kb_agent import config
        from textual.widgets import Button
        app = make_app()
        config.settings = MagicMock()
        async with app.run_test() as pilot:
            app.push_screen(ChatModeScreen(), app._on_chatmode_result)
            await pilot.pause(delay=0.5)
            chat_screen = next(s for s in app.screen_stack if isinstance(s, ChatModeScreen))
            assert chat_screen.query_one("#btn-normal", Button) is not None
            assert chat_screen.query_one("#btn-kb", Button) is not None
            assert chat_screen.query_one("#cancel", Button) is not None


# ─── Keyboard Shortcuts ─────────────────────────────────────────────────────

class TestKeyboardShortcuts:
    async def test_ctrl_l_clears(self):
        app = make_app()
        async with app.run_test() as pilot:
            await pilot.press("ctrl+l")
            await pilot.pause()

    async def test_ctrl_s_opens_settings(self):
        app = make_app()
        async with app.run_test() as pilot:
            await pilot.press("ctrl+s")
            await pilot.pause(delay=0.5)
            assert app.screen.query_one("#settings-dialog") is not None


# ─── Integration ─────────────────────────────────────────────────────────────

class TestIntegration:
    async def test_query_with_engine(self):
        app = make_app()
        async with app.run_test() as pilot:
            mock_engine = MagicMock()
            mock_engine.answer_query.return_value = "Test response"
            app.engine = mock_engine

            ta = app.query_one("#chat-input", ChatInput)
            ta.insert("What is Project X?")
            await pilot.press("enter")
            await pilot.pause(delay=0.5)
            mock_engine.answer_query.assert_called_once()


# ─── Unit Tests ──────────────────────────────────────────────────────────────

class TestSlashCommandsUnit:
    def test_not_empty(self):
        assert len(SLASH_COMMANDS) >= 4

    def test_all_start_with_slash(self):
        for cmd, _ in SLASH_COMMANDS:
            assert cmd.startswith("/")

    def test_all_have_descriptions(self):
        for _, desc in SLASH_COMMANDS:
            assert len(desc) > 0

    def test_no_duplicates(self):
        names = [c for c, _ in SLASH_COMMANDS]
        assert len(names) == len(set(names))

    def test_alphabetically_sorted(self):
        names = [c for c, _ in SLASH_COMMANDS]
        assert names == sorted(names)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
