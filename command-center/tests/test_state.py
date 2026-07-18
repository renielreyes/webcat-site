import tempfile
import unittest
from pathlib import Path

from ccengine.state import Pending, StateStore, now_iso


class TestStateStore(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.path = Path(self.tmp.name) / "sub" / "pending.json"

    def tearDown(self):
        self.tmp.cleanup()

    def test_get_none_when_absent(self):
        self.assertIsNone(StateStore(self.path).get())

    def test_set_get_roundtrip(self):
        store = StateStore(self.path)
        store.set(Pending(task="add a banner", created_ts=now_iso(), pr_number=12, previewed_sha="abc"))
        got = store.get()
        self.assertEqual(got.task, "add a banner")
        self.assertEqual(got.pr_number, 12)
        self.assertEqual(got.previewed_sha, "abc")
        self.assertEqual(got.label, "#12")

    def test_label_building_when_no_pr(self):
        self.assertEqual(Pending(task="t", created_ts=now_iso()).label, "building")

    def test_clear(self):
        store = StateStore(self.path)
        store.set(Pending(task="t", created_ts=now_iso()))
        store.clear()
        self.assertIsNone(store.get())
        store.clear()  # idempotent

    def test_corrupt_returns_none(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text("not json")
        self.assertIsNone(StateStore(self.path).get())


if __name__ == "__main__":
    unittest.main()
