import tempfile
import unittest
from pathlib import Path

from ccengine import commands, config as config_mod
from ccengine.mailbox import MailboxError
from ccengine.provider import ProviderError
from ccengine.state import Pending, StateStore, now_iso


def pr(number, title="t", labels=None, draft=False, sha="sha1"):
    return {"number": number, "title": title, "head_branch": "b",
            "head_sha": sha, "is_draft": draft, "labels": labels or []}


class FakeProvider:
    def __init__(self, prs=None, preview=None, live=None, list_error=False,
                 merge_sha="mergesha1", deploy="success",
                 approve_error=False, merge_error=False):
        self.prs = prs or []
        self.preview = preview
        self.live = live or {"ok": True, "code": 200, "note": "reachable"}
        self.list_error = list_error
        self.labels_added = []
        self.comments_added = []
        # ship knobs
        self.merge_sha = merge_sha
        self.deploy = deploy               # str, or a list consumed one-per-poll
        self.approve_error = approve_error
        self.merge_error = merge_error
        self.approved = []
        self.merged = []
        self._deploy_calls = 0

    def list_open_prs(self):
        if self.list_error:
            raise ProviderError("couldn't reach GitHub")
        return self.prs

    def preview_url(self, n):
        return self.preview

    def add_label(self, n, label):
        self.labels_added.append((n, label))

    def add_comment(self, n, body):
        self.comments_added.append((n, body))

    def live_check(self, url):
        return self.live

    # --- ship boundary ---
    def pr_view(self, n):
        for p in self.prs:
            if p["number"] == n:
                return p
        return None

    def approve_pr(self, n, body="ok"):
        if self.approve_error:
            raise ProviderError("could not approve")
        self.approved.append((n, body))

    def merge_pr(self, n, expected_sha=None):
        if self.merge_error:
            raise ProviderError("base branch policy prohibits the merge")
        self.merged.append((n, expected_sha))

    def default_branch_sha(self, branch="main"):
        return self.merge_sha

    def deploy_conclusion(self, sha, check_name):
        if isinstance(self.deploy, list):
            i = min(self._deploy_calls, len(self.deploy) - 1)
            self._deploy_calls += 1
            return self.deploy[i]
        return self.deploy


class FakeMailbox:
    def __init__(self, fail=False):
        self.fail = fail
        self.written = []

    def write_task(self, md, message="cc"):
        if self.fail:
            raise MailboxError("mailbox unreachable")
        self.written.append((md, message))
        return "mbxsha"


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.cfg = config_mod.load(environ={})
        self.state = StateStore(Path(self.tmp.name) / "pending.json")

    def tearDown(self):
        self.tmp.cleanup()


class TestRun(Base):
    def test_empty_text_refused(self):
        r = commands.run(self.cfg, FakeProvider(), self.state, FakeMailbox(), "   ")
        self.assertEqual(r.outcome, "refused")

    def test_refused_when_already_pending(self):
        self.state.set(Pending(task="old", created_ts=now_iso(), pr_number=5))
        r = commands.run(self.cfg, FakeProvider(), self.state, FakeMailbox(), "new thing")
        self.assertEqual(r.outcome, "refused")
        self.assertIn("#5", r.message)

    def test_refused_when_open_pr_exists(self):
        r = commands.run(self.cfg, FakeProvider(prs=[pr(9)]), self.state, FakeMailbox(), "new thing")
        self.assertEqual(r.outcome, "refused")

    def test_happy_path_queues_and_sets_state(self):
        mbx = FakeMailbox()
        r = commands.run(self.cfg, FakeProvider(prs=[]), self.state, mbx, "add a contact button")
        self.assertEqual(r.outcome, "ok")
        self.assertEqual(len(mbx.written), 1)
        self.assertIn("add a contact button", mbx.written[0][0])   # task text is in the markdown
        self.assertIsNotNone(self.state.get())

    def test_mailbox_failure_reported(self):
        r = commands.run(self.cfg, FakeProvider(prs=[]), self.state, FakeMailbox(fail=True), "x")
        self.assertEqual(r.outcome, "failed")
        self.assertIsNone(self.state.get())   # nothing queued -> no pending


class TestPreview(Base):
    def test_nothing_building(self):
        r = commands.preview(self.cfg, FakeProvider(prs=[]), self.state)
        self.assertEqual(r.outcome, "ok")
        self.assertIn("Nothing is being built", r.message)

    def test_still_building_when_pending_but_no_pr(self):
        self.state.set(Pending(task="x", created_ts=now_iso()))
        r = commands.preview(self.cfg, FakeProvider(prs=[]), self.state)
        self.assertIn("still building", r.message)

    def test_preview_ready_pins_sha(self):
        prov = FakeProvider(prs=[pr(11, "headline", sha="deadbeef")], preview="https://x-11.azurestaticapps.net")
        r = commands.preview(self.cfg, prov, self.state)
        self.assertEqual(r.outcome, "ok")
        self.assertIn("azurestaticapps.net", r.message)
        self.assertEqual(self.state.get().pr_number, 11)
        self.assertEqual(self.state.get().previewed_sha, "deadbeef")

    def test_preview_not_ready(self):
        prov = FakeProvider(prs=[pr(11)], preview=None)
        r = commands.preview(self.cfg, prov, self.state)
        self.assertEqual(r.outcome, "ok")
        self.assertIn("isn't ready yet", r.message)
        self.assertIsNone(self.state.get().previewed_sha)   # not pinned until previewable

    def test_multiple_prs_refused(self):
        r = commands.preview(self.cfg, FakeProvider(prs=[pr(1), pr(2)]), self.state)
        self.assertEqual(r.outcome, "refused")


class TestHold(Base):
    def test_hold_pending_pr(self):
        self.state.set(Pending(task="x", created_ts=now_iso(), pr_number=7))
        prov = FakeProvider()
        r = commands.hold(self.cfg, prov, self.state, note="change the wording")
        self.assertEqual(r.outcome, "ok")
        self.assertIn((7, "held"), prov.labels_added)
        self.assertEqual(len(prov.comments_added), 1)
        self.assertTrue(self.state.get().held)

    def test_hold_discovers_single_pr(self):
        prov = FakeProvider(prs=[pr(8)])
        r = commands.hold(self.cfg, prov, self.state, note="")
        self.assertEqual(r.outcome, "ok")
        self.assertIn((8, "held"), prov.labels_added)
        self.assertEqual(len(prov.comments_added), 0)   # no note -> no comment

    def test_hold_nothing_to_hold(self):
        r = commands.hold(self.cfg, FakeProvider(prs=[]), self.state, note="")
        self.assertEqual(r.outcome, "refused")


class ShipBase(Base):
    """A Base that also has a readable merge key and helpers for a previewed change."""
    def setUp(self):
        super().setUp()
        keyfile = Path(self.tmp.name) / "ship-key"
        keyfile.write_text("ghp_faketoken", encoding="utf-8")
        self.cfg.merge_key_path = str(keyfile)          # ship now sees a merge key
        self.cfg.live_url = "https://example.test"       # keep live_check off the network via the fake

    def previewed(self, number=11, sha="deadbeef", held=False):
        """Put the store in the state `preview` leaves: a pinned, ready-to-ship change."""
        self.state.set(Pending(task="add a contact button", created_ts=now_iso(),
                               pr_number=number, previewed_sha=sha, held=held))

    def ship(self, prov):
        return commands.ship(self.cfg, prov, self.state,
                             sleep=lambda _: None, poll_timeout=0.05, poll_interval=0.01)


class TestShip(ShipBase):
    def test_refused_without_merge_key(self):
        self.cfg.merge_key_path = ""                     # no key on this machine
        self.previewed()
        r = self.ship(FakeProvider(prs=[pr(11, sha="deadbeef")]))
        self.assertEqual(r.outcome, "refused")
        self.assertIn("merge key", r.message)

    def test_refused_when_nothing_pending(self):
        r = self.ship(FakeProvider(prs=[]))
        self.assertEqual(r.outcome, "refused")
        self.assertIn("Nothing is ready to publish", r.message)

    def test_refused_when_not_previewed(self):
        # pending exists (a PR) but was never previewed -> no pinned SHA
        self.state.set(Pending(task="x", created_ts=now_iso(), pr_number=11))
        r = self.ship(FakeProvider(prs=[pr(11)]))
        self.assertEqual(r.outcome, "refused")
        self.assertIn("Preview it first", r.message)

    def test_refused_when_held(self):
        self.previewed(held=True)
        r = self.ship(FakeProvider(prs=[pr(11, sha="deadbeef")]))
        self.assertEqual(r.outcome, "refused")
        self.assertIn("on hold", r.message)

    def test_refused_when_change_moved(self):
        self.previewed(sha="deadbeef")
        # the live PR head is now a different commit than what was previewed
        r = self.ship(FakeProvider(prs=[pr(11, sha="NEWSHA")]))
        self.assertEqual(r.outcome, "refused")
        self.assertIn("updated after you previewed", r.message)
        self.assertIsNotNone(self.state.get())           # still pending; nothing published

    def test_failed_when_pr_gone(self):
        self.previewed()
        r = self.ship(FakeProvider(prs=[]))              # PR no longer open
        self.assertEqual(r.outcome, "failed")
        self.assertIn("couldn't find change #11", r.message)

    def test_happy_path_publishes_and_clears(self):
        self.previewed(number=11, sha="deadbeef")
        prov = FakeProvider(prs=[pr(11, "add a contact button", sha="deadbeef")],
                            merge_sha="mainsha9", deploy="success")
        r = self.ship(prov)
        self.assertEqual(r.outcome, "ok")
        self.assertIn("Published", r.message)
        self.assertEqual(prov.approved, [(11, "Approved & shipped via Command Center (owner).")])
        self.assertEqual(prov.merged, [(11, "deadbeef")])     # merged EXACTLY the previewed head
        self.assertEqual(r.fields["merge_sha"], "mainsha9")   # recorded for undo
        self.assertEqual(r.fields["previewed_sha"], "deadbeef")
        self.assertIsNone(self.state.get())                   # slot cleared for the next change

    def test_deploy_failure_reports_old_site_safe(self):
        self.previewed(number=11, sha="deadbeef")
        prov = FakeProvider(prs=[pr(11, sha="deadbeef")], deploy="failure")
        r = self.ship(prov)
        self.assertEqual(r.outcome, "failed")
        self.assertIn("publish step FAILED", r.message)
        self.assertIn("still up", r.message)
        self.assertIsNone(self.state.get())                   # merge happened; slot still cleared

    def test_deploy_pending_reports_finishing(self):
        self.previewed(number=11, sha="deadbeef")
        prov = FakeProvider(prs=[pr(11, sha="deadbeef")], deploy="pending")
        r = self.ship(prov)
        self.assertEqual(r.outcome, "ok")
        self.assertIn("finishing in the background", r.message)

    def test_deploy_becomes_success_after_polling(self):
        self.previewed(number=11, sha="deadbeef")
        prov = FakeProvider(prs=[pr(11, sha="deadbeef")], deploy=["pending", "pending", "success"])
        r = self.ship(prov)
        self.assertEqual(r.outcome, "ok")
        self.assertIn("Published", r.message)

    def test_merge_error_leaves_site_unchanged(self):
        self.previewed(number=11, sha="deadbeef")
        prov = FakeProvider(prs=[pr(11, sha="deadbeef")], merge_error=True)
        r = self.ship(prov)
        self.assertEqual(r.outcome, "failed")
        self.assertIn("was NOT changed", r.message)
        self.assertIsNotNone(self.state.get())                # merge failed -> change still pending


if __name__ == "__main__":
    unittest.main()
