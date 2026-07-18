import unittest

from ccengine import config as config_mod
from ccengine.provider import ProviderError
from ccengine.status import compute_status, render_status, classify_pr


def pr(number, title="t", labels=None, draft=False, sha="abc123"):
    return {"number": number, "title": title, "head_branch": "b",
            "head_sha": sha, "is_draft": draft, "labels": labels or []}


class FakeProvider:
    def __init__(self, prs=None, live=None, error=None):
        self._prs = prs or []
        self._live = live or {"ok": True, "code": 200, "note": "reachable"}
        self._error = error

    def list_open_prs(self):
        if self._error:
            raise ProviderError(self._error)
        return self._prs

    def live_check(self, url):
        return self._live


class FakeLog:
    def __init__(self, ship=None):
        self._ship = ship

    def last_ship(self):
        return self._ship


class TestClassify(unittest.TestCase):
    def test_held(self):
        self.assertEqual(classify_pr(pr(1, labels=["Held"])), "on hold")

    def test_building(self):
        self.assertEqual(classify_pr(pr(1, draft=True)), "building")

    def test_ready(self):
        self.assertEqual(classify_pr(pr(1)), "ready to review")


class TestStatus(unittest.TestCase):
    def setUp(self):
        self.cfg = config_mod.load(environ={})

    def test_running_vs_paused(self):
        s_run = compute_status(self.cfg, FakeProvider(), FakeLog(), stop_active=False)
        s_paused = compute_status(self.cfg, FakeProvider(), FakeLog(), stop_active=True)
        self.assertEqual(s_run["loop"], "running")
        self.assertEqual(s_paused["loop"], "paused")
        self.assertIn("PAUSED", render_status(s_paused))

    def test_nothing_pending(self):
        s = compute_status(self.cfg, FakeProvider(prs=[]), FakeLog(), stop_active=False)
        self.assertEqual(s["pending"], [])
        self.assertIn("all caught up", render_status(s))

    def test_pending_classified(self):
        prov = FakeProvider(prs=[pr(3, "headline", labels=["held"]), pr(4, "footer")])
        s = compute_status(self.cfg, prov, FakeLog(), stop_active=False)
        states = {p["number"]: p["state"] for p in s["pending"]}
        self.assertEqual(states[3], "on hold")
        self.assertEqual(states[4], "ready to review")

    def test_github_error_degrades_gracefully(self):
        s = compute_status(self.cfg, FakeProvider(error="couldn't reach GitHub"), FakeLog(), stop_active=False)
        self.assertFalse(s["github_ok"])
        self.assertEqual(s["github_error"], "couldn't reach GitHub")
        self.assertIn("couldn't check", render_status(s))

    def test_live_failure_shown(self):
        prov = FakeProvider(live={"ok": False, "code": 503, "note": "HTTP 503"})
        s = compute_status(self.cfg, prov, FakeLog(), stop_active=False)
        self.assertFalse(s["live"]["ok"])
        self.assertIn("NOT reachable", render_status(s))

    def test_last_ship_shown(self):
        s = compute_status(self.cfg, FakeProvider(), FakeLog(ship={"ts": "2026-07-16T00:00:00Z", "title": "new banner"}),
                           stop_active=False)
        self.assertIn("new banner", render_status(s))


if __name__ == "__main__":
    unittest.main()
