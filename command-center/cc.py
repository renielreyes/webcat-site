#!/usr/bin/env python3
"""Command Center — the owner's plain-English control for their site.

Usage:
    cc.py status         Show what's happening (running/paused, pending, last publish, live check).
    cc.py help           Show this help.

Later phases add: run, preview, hold, ship, undo, stop, resume.

Config: defaults are built in; override with a TOML file via CC_CONFIG=/path/to/cc.toml,
or with CC_* environment variables. No secrets in config — see ccengine/config.py.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

# Make the package importable no matter where cc.py is invoked from.
sys.path.insert(0, str(Path(__file__).resolve().parent))

from ccengine import __version__, config as config_mod, log as log_mod, ui  # noqa: E402
from ccengine.provider import GitHubProvider  # noqa: E402
from ccengine.status import compute_status, render_status  # noqa: E402

# Verbs planned for later phases -> the phase they arrive in (friendly "not yet" messaging).
FUTURE = {
    "run": 1, "preview": 1, "hold": 1,
    "stop": 2, "resume": 2,
    "ship": 3, "undo": 3,
}


def _load_config():
    path = os.environ.get("CC_CONFIG")
    if not path:
        default = Path(os.path.expanduser("~/.webcat-loop/cc.toml"))
        path = str(default) if default.exists() else None
    return config_mod.load(path)


def cmd_help() -> int:
    ui.heading(f"Command Center v{__version__}")
    ui.say(__doc__.strip())
    return 0


def cmd_status(cfg) -> int:
    provider = GitHubProvider(cfg.repo_full)
    clog = log_mod.CommandLog(cfg.path("log_file"))
    stop_active = cfg.path("stop_file").exists()
    state = compute_status(cfg, provider, clog, stop_active)
    ui.say(render_status(state))
    return 0


def main(argv: list[str] | None = None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    cmd = (argv[0] if argv else "help").lower()

    if cmd in ("help", "-h", "--help"):
        return cmd_help()

    try:
        cfg = _load_config()
    except config_mod.ConfigError as e:
        ui.error(f"Configuration problem: {e}", "Fix the config file or CC_* variables and try again.")
        return 2

    if cmd == "status":
        return cmd_status(cfg)

    if cmd in FUTURE:
        ui.warn(f"'{cmd}' isn't built yet — it arrives in Phase {FUTURE[cmd]}. "
                f"For now, try:  cc.py status")
        return 0

    ui.error(f"I don't know the command '{cmd}'.",
             "Available now: status, help. (Coming: run, preview, hold, ship, undo, stop, resume.)")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
