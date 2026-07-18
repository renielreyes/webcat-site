"""Write a task to the MAILBOX branch (never `main`), so `run` never redeploys.

The worker's loop reads the task from this branch instead of the deploy branch —
that's the council's fix that decouples "queue a task" from "publish." This writer
uses the GitHub contents API via `gh api` (no local checkout to clobber). It is a
boundary; the command layer takes it as an injected dependency so tests use a fake.
"""
from __future__ import annotations

import base64
import json
import os
import subprocess


TASK_PATH = "handoff/NEXT-TASK.md"


class MailboxError(RuntimeError):
    pass


def _make_gh_api(token: str | None = None):
    def _gh_api(args: list[str], body: dict | None = None, timeout: float = 20.0):
        """Run `gh api ...`; return (returncode, parsed-json-or-None)."""
        stdin = None
        full = ["gh", "api", *args]
        if body is not None:
            full += ["--input", "-"]
            stdin = json.dumps(body)
        env = dict(os.environ)
        if token:
            env["GH_TOKEN"] = token
            env["GITHUB_TOKEN"] = token
        try:
            proc = subprocess.run(full, input=stdin, capture_output=True, text=True, timeout=timeout, env=env)
        except FileNotFoundError:
            raise MailboxError("the GitHub tool (gh) isn't available on this machine")
        except subprocess.TimeoutExpired:
            raise MailboxError("GitHub took too long to respond")
        parsed = None
        if proc.stdout.strip():
            try:
                parsed = json.loads(proc.stdout)
            except json.JSONDecodeError:
                parsed = None
        return proc.returncode, parsed
    return _gh_api


class MailboxWriter:
    def __init__(self, repo_full: str, mailbox_branch: str, base_branch: str = "main", api=None, token: str | None = None):
        self.repo = repo_full
        self.branch = mailbox_branch
        self.base = base_branch
        self._api = api or _make_gh_api(token)

    def _ensure_branch(self) -> None:
        rc, _ = self._api([f"repos/{self.repo}/git/ref/heads/{self.branch}"])
        if rc == 0:
            return
        rc, base_ref = self._api([f"repos/{self.repo}/git/ref/heads/{self.base}"])
        if rc != 0 or not base_ref:
            raise MailboxError(f"couldn't read the base branch '{self.base}'")
        base_sha = base_ref.get("object", {}).get("sha")
        rc, _ = self._api([f"repos/{self.repo}/git/refs"],
                          body={"ref": f"refs/heads/{self.branch}", "sha": base_sha})
        if rc != 0:
            raise MailboxError(f"couldn't create the mailbox branch '{self.branch}'")

    def _current_file_sha(self) -> str | None:
        rc, data = self._api([f"repos/{self.repo}/contents/{TASK_PATH}?ref={self.branch}"])
        if rc == 0 and data:
            return data.get("sha")
        return None

    def write_task(self, task_markdown: str, message: str = "cc: queue task") -> str:
        """Create/update the task file on the mailbox branch. Returns the new commit SHA."""
        self._ensure_branch()
        content_b64 = base64.b64encode(task_markdown.encode("utf-8")).decode("ascii")
        body = {"message": message, "content": content_b64, "branch": self.branch}
        existing = self._current_file_sha()
        if existing:
            body["sha"] = existing
        rc, data = self._api(["-X", "PUT", f"repos/{self.repo}/contents/{TASK_PATH}"], body=body)
        if rc != 0 or not data:
            raise MailboxError("couldn't write the task to the mailbox")
        return data.get("commit", {}).get("sha", "")
