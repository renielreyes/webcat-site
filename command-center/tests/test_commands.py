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
    def __init__(self, prs=None, preview=None, live=None, list_error=False):
        self.prs = prs or []
        self.preview = preview
        self.live = live or {"ok": True, "code": 200, "note": "reachable"}
        self.list_error = list_error
        self.labels_added = []
        self.comments_added = []

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


if __name__ == "__main__":
    unittest.main()
