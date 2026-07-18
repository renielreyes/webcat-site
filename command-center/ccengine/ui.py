"""Plain-English output helpers.

The whole point of the engine is a non-technical owner, so every message is
friendly and jargon-free, and errors NEVER surface raw git/gh text. Color is
used only when writing to a real terminal.
"""
from __future__ import annotations

import sys

_COLORS = {
    "reset": "\033[0m", "dim": "\033[2m", "bold": "\033[1m",
    "green": "\033[32m", "yellow": "\033[33m", "red": "\033[31m", "cyan": "\033[36m",
}


def _c(name: str, stream) -> str:
    return _COLORS.get(name, "") if getattr(stream, "isatty", lambda: False)() else ""


def say(msg: str, stream=None) -> None:
    stream = stream or sys.stdout
    stream.write(msg + "\n")


def ok(msg: str, stream=None) -> None:
    stream = stream or sys.stdout
    say(f"{_c('green', stream)}✓{_c('reset', stream)} {msg}", stream)


def warn(msg: str, stream=None) -> None:
    stream = stream or sys.stdout
    say(f"{_c('yellow', stream)}⚠{_c('reset', stream)} {msg}", stream)


def error(msg: str, hint: str | None = None, stream=None) -> None:
    """A friendly failure: a plain sentence, and (optionally) the next right action.
    Never pass raw git/gh output here — translate it to plain English first."""
    stream = stream or sys.stderr
    say(f"{_c('red', stream)}✗{_c('reset', stream)} {msg}", stream)
    if hint:
        say(f"  {_c('dim', stream)}→ {hint}{_c('reset', stream)}", stream)


def heading(msg: str, stream=None) -> None:
    stream = stream or sys.stdout
    say(f"{_c('bold', stream)}{msg}{_c('reset', stream)}", stream)
