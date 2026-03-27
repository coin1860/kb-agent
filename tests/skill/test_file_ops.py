"""
Unit tests for tools/atomic/file_ops.py
Tests: path traversal blocked, create/overwrite/append/delete, requires_approval flag.
"""

import pytest
from unittest.mock import patch
from pathlib import Path


@pytest.fixture
def data_folder(tmp_path):
    """Temporary data folder."""
    d = tmp_path / "data"
    d.mkdir()
    return d


@pytest.fixture(autouse=True)
def mock_data_folder(data_folder):
    """Patch _get_data_folder and settings to use the tmp data folder."""
    class DummySettings:
        data_folder = str(data_folder)
        output_path = None
        python_code_path = None
        temp_path = None

    with patch("kb_agent.tools.atomic.file_ops._get_data_folder", return_value=data_folder), \
         patch("kb_agent.config.settings", DummySettings()):
        yield data_folder


def _invoke_write_file(**kwargs):
    """Invoke write_file tool with given args."""
    from kb_agent.tools.atomic.file_ops import write_file
    return write_file.invoke(kwargs)


def test_requires_approval_flag():
    from kb_agent.tools.atomic.file_ops import write_file, TOOL_APPROVAL_REGISTRY
    assert TOOL_APPROVAL_REGISTRY.get(write_file.name, False) is True


def test_create_new_file(data_folder):
    result = _invoke_write_file(path="output/test.md", content="# Hello", mode="create")
    assert "Created" in result
    assert (data_folder / "output" / "test.md").read_text() == "# Hello"


def test_create_fails_if_exists(data_folder):
    (data_folder / "output").mkdir(parents=True, exist_ok=True)
    (data_folder / "output" / "existing.md").write_text("old")
    result = _invoke_write_file(path="output/existing.md", content="new", mode="create")
    assert "already exists" in result
    # File unchanged
    assert (data_folder / "output" / "existing.md").read_text() == "old"


def test_overwrite_existing_file(data_folder):
    (data_folder / "output").mkdir(parents=True, exist_ok=True)
    (data_folder / "output" / "file.md").write_text("old content")
    result = _invoke_write_file(path="output/file.md", content="new content", mode="overwrite")
    assert "Overwrote" in result
    assert (data_folder / "output" / "file.md").read_text() == "new content"


def test_append_to_file(data_folder):
    (data_folder / "output").mkdir(parents=True, exist_ok=True)
    (data_folder / "output" / "log.txt").write_text("line1\n")
    result = _invoke_write_file(path="output/log.txt", content="line2\n", mode="append")
    assert "Appended" in result
    assert (data_folder / "output" / "log.txt").read_text() == "line1\nline2\n"


def test_delete_existing_file(data_folder):
    (data_folder / "output").mkdir(parents=True, exist_ok=True)
    f = data_folder / "output" / "delete_me.md"
    f.write_text("temp")
    result = _invoke_write_file(path="output/delete_me.md", mode="delete")
    assert "Deleted" in result
    assert not f.exists()


def test_delete_nonexistent_file(data_folder):
    result = _invoke_write_file(path="output/ghost.md", mode="delete")
    assert "not found" in result.lower() or "nothing to delete" in result.lower()


def test_path_traversal_blocked():
    result = _invoke_write_file(path="../../etc/passwd", content="evil", mode="overwrite")
    assert "SecurityError" in result


def test_absolute_path_outside_blocked(data_folder):
    result = _invoke_write_file(path="/tmp/evil.md", content="evil", mode="create")
    assert "SecurityError" in result


def test_invalid_mode():
    result = _invoke_write_file(path="output/test.md", content="x", mode="execute")
    assert "invalid mode" in result.lower()


def test_creates_parent_directories(data_folder):
    result = _invoke_write_file(
        path="output/deep/nested/dir/file.md",
        content="hi",
        mode="create"
    )
    assert "Created" in result
    assert (data_folder / "output" / "deep" / "nested" / "dir" / "file.md").exists()
