#!/usr/bin/env python3
"""Command Center — the owner's plain-English control for their site.

Usage:
    cc.py status            Show what's happening (running/paused, pending, last publish, live check).
    cc.py run "<what>"      Start a change — hand a plain-English task to the builder.
    cc.py preview           See the pending change on a private test link (not live).
    cc.py hold [note]       Park the pending change so it won't publish.
    cc.py stop              Pause everything now (nothing new builds or publishes).
    cc.py resume            Un-pause.
    cc.py help              Show this help.

Later phases add: ship, undo (3).

Config: built-in defaults; override with a TOML file via CC_CONFIG=/path/to/cc.toml,
or with CC_* environment variables. No secrets in config — see ccengine/config.py.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from ccengine import __version__, commands, config as config_mod, log as log_mod, ui  # noqa: E402
from ccengine.lock import Busy, SingleFlight  # noqa: E402
from ccengine.mailbox import MailboxWriter  # noqa: E402
from ccengine.provider import GitHubProvider  # noqa: E402
from ccengine.state import StateStore  # noqa: E402
from ccengine.status import compute_status, render_status  # noqa: E402

FUTURE = {"ship": 3, "undo": 3}


def _load_config():
    path = os.environ.get("CC_CONFIG")
    if not path:
        default = Path(os.path.expanduser("~/.webcat-loop/cc.toml"))
        path = str(default) if default.exists() else None
    return config_mod.load(path)


def _emit(result) -> int:
    if result.outcome == "ok":
        ui.say(result.message)
    elif result.outcome == "refused":
        ui.warn(result.message)
    else:
        ui.error(result.message)
    return result.exit_code


def _deps(cfg):
    provider = GitHubProvider(cfg.repo_full)
    state = StateStore(cfg.path("state_file"))
    mailbox = MailboxWriter(cfg.repo_full, cfg.mailbox_branch)
    clog = log_mod.CommandLog(cfg.path("log_file"))
    return provider, state, mailbox, clog


def _run_mutating(cfg, cmd: str, fn) -> int:
    """Shared wrapper for commands that change something: pause-check, single-flight lock, write-ahead log."""
    if cfg.path("stop_file").exists():
        ui.warn("The loop is paused — type  resume  first.")
        return 0
    _, _, _, clog = _deps(cfg)
    try:
        with SingleFlight(cfg.path("lock_file")):
            cid = clog.intent(cmd, actor=cfg.owner_username)
            result = fn()
            clog.result(cid, result.outcome, command_kind=cmd, **result.fields)
            return _emit(result)
    except Busy:
        ui.warn("Another Command Center action is already running — give it a second and try again.")
        return 0


def _run_logged(cfg, cmd: str, fn) -> int:
    """For stop/resume: logged, but NO lock and NO pause-check — a kill switch must always work instantly."""
    clog = log_mod.CommandLog(cfg.path("log_file"))
    cid = clog.intent(cmd, actor=cfg.owner_username)
    result = fn()
    clog.result(cid, result.outcome, command_kind=cmd, **result.fields)
    return _emit(result)


def cmd_help() -> int:
    ui.heading(f"Command Center v{__version__}")
    ui.say(__doc__.strip())
    return 0


def cmd_status(cfg) -> int:
    provider, state, _, clog = _deps(cfg)
    stop_active = cfg.path("stop_file").exists()
    ui.say(render_status(compute_status(cfg, provider, clog, stop_active)))
    return 0


def main(argv: list[str] | None = None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    cmd = (argv[0] if argv else "help").lower()
    rest = argv[1:]

    if cmd in ("help", "-h", "--help"):
        return cmd_help()

    try:
        cfg = _load_config()
    except config_mod.ConfigError as e:
        ui.error(f"Configuration problem: {e}", "Fix the config file or CC_* variables and try again.")
        return 2

    if cmd == "status":
        return cmd_status(cfg)

    if cmd == "run":
        provider, state, mailbox, _ = _deps(cfg)
        return _run_mutating(cfg, "run", lambda: commands.run(cfg, provider, state, mailbox, " ".join(rest)))

    if cmd == "preview":
        provider, state, _, _ = _deps(cfg)
        return _emit(commands.preview(cfg, provider, state))  # read-only: no lock

    if cmd == "hold":
        provider, state, _, _ = _deps(cfg)
        return _run_mutating(cfg, "hold", lambda: commands.hold(cfg, provider, state, " ".join(rest)))

    if cmd == "stop":
        return _run_logged(cfg, "stop", lambda: commands.stop(cfg))

    if cmd == "resume":
        return _run_logged(cfg, "resume", lambda: commands.resume(cfg))

    if cmd in FUTURE:
        ui.warn(f"'{cmd}' isn't built yet — it arrives in Phase {FUTURE[cmd]}. For now, try:  cc.py status")
        return 0

    ui.error(f"I don't know the command '{cmd}'.",
             "Available now: status, run, preview, hold, stop, resume, help. (Coming: ship, undo.)")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
