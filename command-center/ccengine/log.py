"""Write-ahead, append-only command log (JSON Lines).

Every mutating command records its INTENT *before* it acts and its RESULT
*after*, so a crash mid-command leaves a discoverable in-flight record that can
be reconciled against real GitHub state. Read-only commands (e.g. `status`) are
not logged. The authoritative record of what shipped is GitHub itself (merge
commits / PR events); this local log is a tamper-resistant convenience copy.

Format: one JSON object per line. The file is opened append-only and fsync'd.
Never edit or delete existing lines.
"""
from __future__ import annotations

import json
import os
import uuid
from datetime import datetime, timezone
from pathlib import Path


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class CommandLog:
    def __init__(self, path: str | os.PathLike):
        self.path = Path(os.path.expanduser(str(path)))
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def _append(self, record: dict) -> None:
        line = json.dumps(record, ensure_ascii=False, sort_keys=True)
        # Open per-write in append mode so concurrent writers never truncate.
        fd = os.open(self.path, os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o600)
        try:
            os.write(fd, (line + "\n").encode("utf-8"))
            os.fsync(fd)
        finally:
            os.close(fd)

    def intent(self, command: str, actor: str, inputs: dict | None = None) -> str:
        """Record that a command is about to act. Returns a correlation id to pass to result()."""
        cid = uuid.uuid4().hex[:12]
        self._append({
            "id": cid, "ts": _now_iso(), "phase": "intent",
            "command": command, "actor": actor, "inputs": inputs or {},
        })
        return cid

    def result(self, cid: str, outcome: str, **fields) -> None:
        """Record how a command finished. outcome e.g. 'ok' | 'failed' | 'aborted' | 'busy'."""
        rec = {"id": cid, "ts": _now_iso(), "phase": "result", "outcome": outcome}
        rec.update(fields)
        self._append(rec)

    def entries(self) -> list[dict]:
        if not self.path.exists():
            return []
        out = []
        for line in self.path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                out.append(json.loads(line))
            except json.JSONDecodeError:
                continue  # never let a corrupt line break a read
        return out

    def last_ship(self) -> dict | None:
        """The most recent successful ship result, or None."""
        for rec in reversed(self.entries()):
            if rec.get("phase") == "result" and rec.get("command_kind") == "ship" and rec.get("outcome") == "ok":
                return rec
        return None
