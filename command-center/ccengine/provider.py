"""The external boundary: everything that talks to GitHub (`gh`) or the live site
(HTTP) goes through here, so the rest of the engine can be tested with a fake.

Design rule (from the review): tests assert on the REAL system boundary, never
the runner's own stdout — so this adapter is the seam where a FakeProvider is
injected.
"""
from __future__ import annotations

import json
import os
import re
import subprocess
import urllib.error
import urllib.request

_PREVIEW_RE = re.compile(r"https://[A-Za-z0-9.\-]+\.azurestaticapps\.net[^\s)\"']*")


class ProviderError(RuntimeError):
    """A failure talking to GitHub or the live site (already plain-English-ish)."""


class GitHubProvider:
    def __init__(self, repo_full: str, timeout: float = 15.0, token: str | None = None):
        self.repo_full = repo_full
        self.timeout = timeout
        self._token = token   # the runner's merge key, injected as GH_TOKEN for gh calls (ship/undo etc.)

    def _env(self) -> dict:
        env = dict(os.environ)
        if self._token:
            env["GH_TOKEN"] = self._token
            env["GITHUB_TOKEN"] = self._token
        return env

    # --- GitHub ---
    def list_open_prs(self) -> list[dict]:
        """Open PRs as normalized dicts: number, title, head_branch, head_sha, is_draft, labels."""
        out = self._run_gh(["pr", "list", "--repo", self.repo_full, "--state", "open",
                            "--json", "number,title,headRefName,headRefOid,isDraft,labels"])
        try:
            raw = json.loads(out or "[]")
        except json.JSONDecodeError:
            raise ProviderError("GitHub returned something unexpected")
        return [self._normalize_pr(p) for p in raw]

    @staticmethod
    def _normalize_pr(p: dict) -> dict:
        return {
            "number": p.get("number"),
            "title": p.get("title", ""),
            "head_branch": p.get("headRefName", ""),
            "head_sha": p.get("headRefOid", ""),
            "is_draft": bool(p.get("isDraft", False)),
            "labels": [l.get("name", "") for l in (p.get("labels") or [])],
        }

    def _run_gh(self, args: list[str]) -> str:
        try:
            proc = subprocess.run(["gh", *args], capture_output=True, text=True,
                                  timeout=self.timeout, env=self._env())
        except FileNotFoundError:
            raise ProviderError("the GitHub tool (gh) isn't available on this machine")
        except subprocess.TimeoutExpired:
            raise ProviderError("GitHub took too long to respond")
        if proc.returncode != 0:
            raise ProviderError((proc.stderr.strip().splitlines() or ["a GitHub command failed"])[-1])
        return proc.stdout

    # --- publish operations (ship/undo) — need the merge key ---
    def approve_pr(self, number: int, body: str = "Shipped via Command Center") -> None:
        """Submit an approving review (satisfies 'require approvals' — the ship IS the approval)."""
        self._run_gh(["pr", "review", str(number), "--repo", self.repo_full, "--approve", "-b", body])

    def merge_pr(self, number: int, expected_sha: str | None = None) -> None:
        """Merge the PR. If expected_sha is given, merge ONLY that exact head (refuses if it moved)."""
        args = ["pr", "merge", str(number), "--repo", self.repo_full, "--merge"]
        if expected_sha:
            args += ["--match-head-commit", expected_sha]
        self._run_gh(args)

    def deploy_conclusion(self, sha: str, check_name: str) -> str | None:
        """The named deploy check's conclusion on a commit: 'success'|'failure'|... or None if not finished/seen."""
        try:
            out = self._run_gh(["api", f"repos/{self.repo_full}/commits/{sha}/check-runs"])
            runs = json.loads(out).get("check_runs", [])
        except (ProviderError, json.JSONDecodeError):
            return None
        for r in runs:
            if r.get("name") == check_name:
                if r.get("status") != "completed":
                    return "pending"
                return r.get("conclusion")
        return None

    def default_branch_sha(self, branch: str = "main") -> str | None:
        try:
            out = self._run_gh(["api", f"repos/{self.repo_full}/commits/{branch}", "--jq", ".sha"])
            return out.strip() or None
        except ProviderError:
            return None

    def pr_view(self, number: int) -> dict | None:
        """One PR by number, normalized — or None if it isn't found/open."""
        try:
            out = self._run_gh(["pr", "view", str(number), "--repo", self.repo_full,
                                "--json", "number,title,headRefName,headRefOid,isDraft,labels,state"])
        except ProviderError:
            return None
        try:
            return self._normalize_pr(json.loads(out))
        except json.JSONDecodeError:
            return None

    def preview_url(self, number: int) -> str | None:
        """The Azure SWA per-PR preview URL, scraped from the PR's comments (or None if not posted yet)."""
        out = self._run_gh(["pr", "view", str(number), "--repo", self.repo_full, "--json", "comments"])
        try:
            comments = json.loads(out).get("comments", [])
        except json.JSONDecodeError:
            return None
        found = None
        for c in comments:  # take the most recent match
            for m in _PREVIEW_RE.findall(c.get("body", "")):
                found = m
        return found

    def ensure_label(self, name: str, color: str = "EDAE49", desc: str = "") -> None:
        # --force creates the label or updates it if it already exists (idempotent).
        self._run_gh(["label", "create", name, "--repo", self.repo_full, "-c", color, "-d", desc, "--force"])

    def add_label(self, number: int, label: str) -> None:
        self.ensure_label(label, desc="parked by Command Center — not to be published")
        self._run_gh(["pr", "edit", str(number), "--repo", self.repo_full, "--add-label", label])

    def add_comment(self, number: int, body: str) -> None:
        self._run_gh(["pr", "comment", str(number), "--repo", self.repo_full, "--body", body])

    # --- live site ---
    def live_check(self, url: str) -> dict:
        """HTTP GET the live URL. Returns {ok, code, note}. Never raises."""
        req = urllib.request.Request(url, method="GET", headers={"User-Agent": "cc-status/0"})
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                code = resp.getcode()
                return {"ok": 200 <= code < 400, "code": code, "note": "reachable"}
        except urllib.error.HTTPError as e:
            return {"ok": False, "code": e.code, "note": f"HTTP {e.code}"}
        except (urllib.error.URLError, TimeoutError, OSError) as e:
            return {"ok": False, "code": None, "note": f"unreachable ({e.__class__.__name__})"}
