"""Single-flight lock for MUTATING commands.

Two commands must never race a merge and a revert into a broken `main`. This is
the runner's OWN lock, separate from the caged worker's. Read-only commands
(status) do not take it. The holder's PID is recorded in the lock file so a
future `stop` can signal an in-flight command (Phase 2/3).
"""
from __future__ import annotations

import fcntl
import os
from pathlib import Path


class Busy(Exception):
    """Raised when another command already holds the single-flight lock."""


class SingleFlight:
    def __init__(self, path: str | os.PathLike):
        self.path = Path(os.path.expanduser(str(path)))
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._fd = None

    def __enter__(self) -> "SingleFlight":
        self._fd = os.open(self.path, os.O_WRONLY | os.O_CREAT, 0o600)
        try:
            fcntl.flock(self._fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError:
            os.close(self._fd)
            self._fd = None
            raise Busy("another Command Center action is already running")
        # Record holder PID for a future stop-abort; truncate then write.
        os.ftruncate(self._fd, 0)
        os.write(self._fd, str(os.getpid()).encode("ascii"))
        os.fsync(self._fd)
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        if self._fd is not None:
            try:
                fcntl.flock(self._fd, fcntl.LOCK_UN)
            finally:
                os.close(self._fd)
                self._fd = None

    def holder_pid(self) -> int | None:
        """Best-effort read of the recorded holder PID (for diagnostics / stop)."""
        try:
            txt = self.path.read_text().strip()
            return int(txt) if txt else None
        except (OSError, ValueError):
            return None
