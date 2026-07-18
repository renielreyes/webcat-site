"""The single in-flight change ("pending") state.

The engine enforces ONE change in flight at a time, so `preview`/`ship` are never
ambiguous (and we stay within the free-tier preview cap). This little store tracks
that one change: the task text, the PR the worker opened for it, the SHA the owner
previewed (so `ship` can pin to exactly what was reviewed), and whether it's held.
Stored as a single JSON file; cleared when the change ships or is discarded.
"""
from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass
class Pending:
    task: str
    created_ts: str
    pr_number: int | None = None
    previewed_sha: str | None = None
    held: bool = False
    note: str = ""

    @property
    def label(self) -> str:
        return f"#{self.pr_number}" if self.pr_number else "building"


class StateStore:
    def __init__(self, path: str | os.PathLike):
        self.path = Path(os.path.expanduser(str(path)))
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def get(self) -> Pending | None:
        if not self.path.exists():
            return None
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
            return Pending(**data)
        except (json.JSONDecodeError, TypeError, ValueError):
            return None

    def set(self, pending: Pending) -> None:
        tmp = self.path.with_suffix(".tmp")
        tmp.write_text(json.dumps(asdict(pending), ensure_ascii=False, sort_keys=True), encoding="utf-8")
        os.replace(tmp, self.path)  # atomic

    def clear(self) -> None:
        try:
            self.path.unlink()
        except FileNotFoundError:
            pass
