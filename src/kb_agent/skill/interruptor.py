"""
Interrupt handler — SIGINT / Ctrl+C cancellation token for the skill executor.
"""

from __future__ import annotations

import signal
import subprocess
import threading
from typing import Optional


class CancellationToken:
    """
    Thread-safe cancellation signal.

    Wraps threading.Event. The executor checks .is_set() at each step boundary.
    """

    def __init__(self):
        self._event = threading.Event()

    def cancel(self) -> None:
        """Signal cancellation."""
        self._event.set()

    def reset(self) -> None:
        """Clear the cancellation flag (e.g., after user chooses 'continue')."""
        self._event.clear()

    def is_set(self) -> bool:
        """Return True if cancellation has been requested."""
        return self._event.is_set()

    def check(self) -> bool:
        """Alias for is_set() — check if cancellation was requested."""
        return self._event.is_set()


class InterruptHandler:
    """
    Registers a SIGINT (Ctrl+C) handler that sets the CancellationToken
    and optionally terminates an active subprocess.

    Usage:
        token = CancellationToken()
        handler = InterruptHandler(token)
        with handler:
            # executor loop here
    """

    def __init__(self, token: CancellationToken):
        self.token = token
        self._active_process: Optional[subprocess.Popen] = None
        self._previous_handler = None
        self._lock = threading.Lock()

    def set_active_process(self, proc: Optional[subprocess.Popen]) -> None:
        """Register the current subprocess so it can be killed on interrupt."""
        with self._lock:
            self._active_process = proc

    def _handle_sigint(self, signum, frame) -> None:
        """SIGINT handler: set token and kill any active subprocess."""
        self.token.cancel()
        with self._lock:
            if self._active_process is not None:
                try:
                    self._active_process.terminate()
                except Exception:
                    pass

    def __enter__(self):
        self._previous_handler = signal.signal(signal.SIGINT, self._handle_sigint)
        return self

    def __exit__(self, *args):
        if self._previous_handler is not None:
            signal.signal(signal.SIGINT, self._previous_handler)
        return False
