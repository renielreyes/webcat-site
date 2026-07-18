"""Configuration for the Command Center engine.

Load order (later overrides earlier): built-in defaults -> a TOML config file ->
environment variables (CC_*). No secrets live here — the merge key used by the
future ship/undo commands is referenced only by a filesystem PATH, read at use
time; its value is never stored in config or the repo.
"""
from __future__ import annotations

import os
import tomllib
from dataclasses import dataclass, fields
from pathlib import Path


DEFAULTS = {
    # Where the worker's clone of the repo lives on this machine.
    "repo_dir": "~/projects/webcat-site",
    # "owner/name" of the GitHub repo this engine operates on.
    "repo_full": "renielreyes/webcat-site",
    # The task mailbox lives OFF the deploy branch so `run` never redeploys.
    "mailbox_branch": "mailbox",
    # Local, instant kill switch (checked before any network call).
    "stop_file": "~/.webcat-loop/STOP",
    # Append-only, write-ahead command log (JSON lines).
    "log_file": "~/.webcat-loop/command-log.jsonl",
    # Single-flight lock for mutating commands.
    "lock_file": "~/.webcat-loop/runner.lock",
    # The live site URL (used by status/ship/undo to confirm a deploy is really live).
    "live_url": "https://purple-meadow-0b838cc0f.7.azurestaticapps.net",
    # Identities (informational + used to classify PR authorship).
    "owner_username": "renielreyes",
    "robot_username": "webcat-worker-bot",
    # PATH to the owner merge key for ship/undo (Phase 3). Empty until provided by
    # the human at deploy time. NEVER put the key value here — only its path.
    "merge_key_path": "",
}

REQUIRED = ["repo_dir", "repo_full", "live_url"]


@dataclass
class Config:
    repo_dir: str
    repo_full: str
    mailbox_branch: str
    stop_file: str
    log_file: str
    lock_file: str
    live_url: str
    owner_username: str
    robot_username: str
    merge_key_path: str

    # --- convenience accessors (expanded, absolute paths) ---
    def path(self, key: str) -> Path:
        return Path(os.path.expanduser(getattr(self, key))).expanduser()

    @property
    def repo_owner(self) -> str:
        return self.repo_full.split("/", 1)[0]

    @property
    def repo_name(self) -> str:
        return self.repo_full.split("/", 1)[1] if "/" in self.repo_full else self.repo_full


class ConfigError(ValueError):
    pass


def load(config_path: str | os.PathLike | None = None, environ: dict | None = None) -> Config:
    """Build a Config from defaults, an optional TOML file, and CC_* env vars."""
    environ = os.environ if environ is None else environ
    values = dict(DEFAULTS)

    if config_path:
        p = Path(os.path.expanduser(str(config_path)))
        if not p.exists():
            raise ConfigError(f"Config file not found: {p}")
        with p.open("rb") as fh:
            file_values = tomllib.load(fh)
        for k, v in file_values.items():
            if k in values:
                values[k] = v

    # Environment overrides: CC_REPO_DIR, CC_LIVE_URL, ...
    for k in values:
        env_key = "CC_" + k.upper()
        if env_key in environ and environ[env_key] != "":
            values[k] = environ[env_key]

    for k in REQUIRED:
        if not str(values.get(k, "")).strip():
            raise ConfigError(f"Required config value is missing or empty: {k}")

    known = {f.name for f in fields(Config)}
    return Config(**{k: values[k] for k in known})
