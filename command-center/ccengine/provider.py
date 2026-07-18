"""The external boundary: everything that talks to GitHub (`gh`) or the live site
(HTTP) goes through here, so the rest of the engine can be tested with a fake.

Design rule (from the review): tests assert on the REAL system boundary, never
the runner's own stdout — so this adapter is the seam where a FakeProvider is
injected.
"""
from __future__ import annotations

import json
import subprocess
import urllib.error
import urllib.request


class ProviderError(RuntimeError):
    """A failure talking to GitHub or the live site (already plain-English-ish)."""


class GitHubProvider:
    def __init__(self, repo_full: str, timeout: float = 15.0):
        self.repo_full = repo_full
        self.timeout = timeout

    # --- GitHub ---
    def list_open_prs(self) -> list[dict]:
        """Open PRs as normalized dicts: number, title, head_branch, head_sha, is_draft, labels."""
        try:
            proc = subprocess.run(
                ["gh", "pr", "list", "--repo", self.repo_full, "--state", "open",
                 "--json", "number,title,headRefName,headRefOid,isDraft,labels"],
                capture_output=True, text=True, timeout=self.timeout,
            )
        except FileNotFoundError:
            raise ProviderError("the GitHub tool (gh) isn't available on this machine")
        except subprocess.TimeoutExpired:
            raise ProviderError("GitHub took too long to respond")
        if proc.returncode != 0:
            raise ProviderError("couldn't reach GitHub (check the sign-in)")
        try:
            raw = json.loads(proc.stdout or "[]")
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
