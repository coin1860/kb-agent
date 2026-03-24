"""
Unit tests for tools/atomic/code_exec.py
Tests: stdout captured, timeout triggers termination, path guard, requires_approval.
"""

import sys
import textwrap
from pathlib import Path
from unittest.mock import patch

import pytest


@pytest.fixture
def python_code_dir(tmp_path):
    d = tmp_path / "python_code"
    d.mkdir()
    return d


@pytest.fixture(autouse=True)
def mock_python_code_path(python_code_dir):
    with patch("kb_agent.tools.atomic.code_exec._get_python_code_path", return_value=python_code_dir):
        yield python_code_dir


def _invoke_run_python(**kwargs):
    from kb_agent.tools.atomic.code_exec import run_python
    return run_python.invoke(kwargs)


def test_requires_approval_flag():
    from kb_agent.tools.atomic.code_exec import run_python, TOOL_APPROVAL_REGISTRY
    assert TOOL_APPROVAL_REGISTRY.get(run_python.name, False) is True


def test_successful_script_stdout_captured(python_code_dir):
    script = python_code_dir / "hello.py"
    script.write_text("print('hello world')")

    result = _invoke_run_python(script_path=str(script))

    assert "exit_code: 0" in result
    assert "hello world" in result
    assert "status: completed" in result


def test_log_file_written(python_code_dir):
    script = python_code_dir / "logtest.py"
    script.write_text("print('check log')")

    _invoke_run_python(script_path=str(script))

    log_path = Path(str(script) + ".log")
    assert log_path.exists()
    assert "check log" in log_path.read_text()


def test_stderr_captured(python_code_dir):
    script = python_code_dir / "err.py"
    script.write_text("import sys; sys.stderr.write('an error\\n')")

    result = _invoke_run_python(script_path=str(script))
    assert "an error" in result


def test_nonzero_exit_code(python_code_dir):
    script = python_code_dir / "fail.py"
    script.write_text("raise ValueError('intentional')")

    result = _invoke_run_python(script_path=str(script))
    assert "exit_code: 1" in result


def test_timeout_triggers_termination(python_code_dir):
    script = python_code_dir / "slow.py"
    script.write_text("import time; time.sleep(60)")

    result = _invoke_run_python(script_path=str(script), timeout_seconds=1)

    assert "timeout" in result.lower()
    assert "exit_code: -1" in result


def test_path_outside_python_code_dir_blocked():
    result = _invoke_run_python(script_path="/tmp/evil.py")
    assert "SecurityError" in result


def test_path_traversal_blocked(python_code_dir):
    result = _invoke_run_python(script_path="../../etc/passwd")
    # Either SecurityError or "not found" — either way not executed
    assert "SecurityError" in result or "not found" in result


def test_script_not_found_returns_error(python_code_dir):
    result = _invoke_run_python(script_path=str(python_code_dir / "nonexistent.py"))
    assert "not found" in result.lower() or "Error" in result
