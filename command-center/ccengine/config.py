"""Configuration for the Command Center engine.

Load order (later overrides earlier): built-in defaults -> a TOML config file ->
environment variables (CC_*). No secrets live here — the merge key used by the
ship/undo commands is referenced only by a filesystem PATH, read at use time; its
value is never stored in config or the repo.

MULTI-PROJECT ISOLATION (council fix, 2026-07-18): each project's runtime state
(pending change, lock, stop flag, command log) is DERIVED from a single per-project
`state_dir`. Two projects must never share these paths — `assert_no_collisions()`
enforces that structurally, so a second project can never read the first's pending
change and ship the wrong PR.
"""
from __future__ import annotations

import os
import tomllib
from dataclasses import dataclass, fields
from pathlib import Path


# The four runtime-state files are DERIVED from state_dir (basename shown here) unless
# the user sets them explicitly. This is what makes per-project isolation structural:
# give a project a unique state_dir and all four move with it.
RUNTIME_DERIVED = {
    "stop_file": "STOP",
    "log_file": "command-log.jsonl",
    "state_file": "pending.json",
    "lock_file": "runner.lock",
}

# Supported deploy targets. 'azure_swa' = a website on Azure Static Web Apps (poll the
# deploy check + live-check the URL). 'none' = a code project with no website (ship =
# merge; no preview URL, no live-check). An unrecognized kind is refused rather than
# silently mis-handled (e.g. polling a deploy check that never appears).
DEPLOY_KINDS = ("azure_swa", "none")


DEFAULTS = {
    # Where the worker's clone of the repo lives on this machine.
    "repo_dir": "~/projects/webcat-site",
    # "owner/name" of the GitHub repo this engine operates on.
    "repo_full": "renielreyes/webcat-site",
    # The task mailbox lives OFF the deploy branch so `run` never redeploys.
    "mailbox_branch": "mailbox",
    # PER-PROJECT runtime-state root. stop/log/state/lock are derived from this (below).
    # Each project MUST have its own; assert_no_collisions() refuses overlap.
    "state_dir": "~/.webcat-loop",
    # Derived from state_dir unless explicitly overridden (see RUNTIME_DERIVED).
    "stop_file": "~/.webcat-loop/STOP",
    "log_file": "~/.webcat-loop/command-log.jsonl",
    "state_file": "~/.webcat-loop/pending.json",
    "lock_file": "~/.webcat-loop/runner.lock",
    # The live site URL (used by status/ship to confirm a deploy is really live).
    "live_url": "https://purple-meadow-0b838cc0f.7.azurestaticapps.net",
    # Identities (informational + used to classify PR authorship).
    "owner_username": "renielreyes",
    "robot_username": "webcat-worker-bot",
    # PATH to the owner merge key for ship/undo. Empty until provided by the human at
    # deploy time. NEVER put the key value here — only its path.
    "merge_key_path": "",
    # The CI check that means "the live deploy finished" (Azure SWA's job name).
    "deploy_check": "Build and Deploy Job",
    # How this project publishes — see DEPLOY_KINDS.
    "deploy_kind": "azure_swa",
}

REQUIRED = ["repo_dir", "repo_full", "live_url", "state_dir"]


@dataclass
class Config:
    repo_dir: str
    repo_full: str
    mailbox_branch: str
    state_dir: str
    stop_file: str
    log_file: str
    state_file: str
    lock_file: str
    live_url: str
    owner_username: str
    robot_username: str
    merge_key_path: str
    deploy_check: str
    deploy_kind: str

    # --- convenience accessors (expanded, absolute paths) ---
    def path(self, key: str) -> Path:
        return Path(os.path.expanduser(getattr(self, key))).expanduser()

    def merge_token(self) -> str | None:
        """Read the owner merge key from its locked file (ship/undo only). None if not configured."""
        if not self.merge_key_path.strip():
            return None
        p = self.path("merge_key_path")
        try:
            tok = p.read_text(encoding="utf-8").strip()
        except OSError:
            return None
        return tok or None

    @property
    def repo_owner(self) -> str:
        return self.repo_full.split("/", 1)[0]

    @property
    def repo_name(self) -> str:
        return self.repo_full.split("/", 1)[1] if "/" in self.repo_full else self.repo_full

    @property
    def project_label(self) -> str:
        """A human name for this project (used in isolation errors / status)."""
        return self.repo_full or str(self.state_dir)


class ConfigError(ValueError):
    pass


def load(config_path: str | os.PathLike | None = None, environ: dict | None = None) -> Config:
    """Build a Config from defaults, an optional TOML file, and CC_* env vars.

    Runtime-state paths (stop/log/state/lock) are DERIVED from state_dir unless the
    caller set them explicitly, so a per-project config only needs a unique state_dir
    to be fully isolated. Backward-compatible: the default state_dir reproduces the
    original ~/.webcat-loop/* paths exactly.
    """
    environ = os.environ if environ is None else environ
    values = dict(DEFAULTS)
    explicit: set[str] = set()   # keys the user actually set (file or env)

    if config_path:
        p = Path(os.path.expanduser(str(config_path)))
        if not p.exists():
            raise ConfigError(f"Config file not found: {p}")
        with p.open("rb") as fh:
            file_values = tomllib.load(fh)
        for k, v in file_values.items():
            if k in values:
                values[k] = v
                explicit.add(k)

    # Environment overrides: CC_REPO_DIR, CC_LIVE_URL, CC_STATE_DIR, ...
    for k in list(values):
        env_key = "CC_" + k.upper()
        if env_key in environ and environ[env_key] != "":
            values[k] = environ[env_key]
            explicit.add(k)

    # Derive per-project runtime paths from state_dir unless the user pinned them.
    for key, base in RUNTIME_DERIVED.items():
        if key not in explicit:
            values[key] = os.path.join(values["state_dir"], base)

    if values["deploy_kind"] not in DEPLOY_KINDS:
        raise ConfigError(
            f"Unknown deploy_kind '{values['deploy_kind']}' — must be one of {', '.join(DEPLOY_KINDS)}.")

    for k in REQUIRED:
        if not str(values.get(k, "")).strip():
            raise ConfigError(f"Required config value is missing or empty: {k}")

    known = {f.name for f in fields(Config)}
    return Config(**{k: values[k] for k in known})


def assert_no_collisions(configs: list[Config]) -> None:
    """Refuse a set of projects whose derived runtime paths overlap (isolation invariant).

    The multi-project registry calls this at load time: if two projects would share a
    state/lock/stop/log file, one project's `ship` could act on the other's in-flight
    change. Fail loudly instead. Each project needs its own state_dir.
    """
    seen: dict[str, str] = {}
    for cfg in configs:
        for key in RUNTIME_DERIVED:
            p = str(cfg.path(key))
            if p in seen and seen[p] != cfg.project_label:
                raise ConfigError(
                    f"Projects '{seen[p]}' and '{cfg.project_label}' share {key} ({p}). "
                    "Give each project its own state_dir so their in-flight changes can't collide.")
            seen[p] = cfg.project_label
