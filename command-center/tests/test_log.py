import json
import tempfile
import unittest
from pathlib import Path

from ccengine.log import CommandLog


class TestCommandLog(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.path = Path(self.tmp.name) / "sub" / "command-log.jsonl"

    def tearDown(self):
        self.tmp.cleanup()

    def test_intent_then_result_are_both_appended(self):
        clog = CommandLog(self.path)
        cid = clog.intent("ship", actor="owner", inputs={"pr": 12})
        clog.result(cid, "ok", command_kind="ship", after_sha="deadbeef")
        entries = clog.entries()
        self.assertEqual(len(entries), 2)
        self.assertEqual(entries[0]["phase"], "intent")
        self.assertEqual(entries[0]["id"], cid)
        self.assertEqual(entries[1]["phase"], "result")
        self.assertEqual(entries[1]["outcome"], "ok")

    def test_append_only_across_instances(self):
        CommandLog(self.path).intent("run", actor="owner")
        CommandLog(self.path).intent("run", actor="owner")  # a fresh instance must not truncate
        self.assertEqual(len(CommandLog(self.path).entries()), 2)

    def test_last_ship_returns_most_recent_ok_ship(self):
        clog = CommandLog(self.path)
        c1 = clog.intent("ship", actor="owner")
        clog.result(c1, "ok", command_kind="ship", title="first")
        c2 = clog.intent("ship", actor="owner")
        clog.result(c2, "ok", command_kind="ship", title="second")
        self.assertEqual(clog.last_ship()["title"], "second")

    def test_last_ship_none_when_no_ship(self):
        clog = CommandLog(self.path)
        clog.result(clog.intent("run", actor="owner"), "ok", command_kind="run")
        self.assertIsNone(clog.last_ship())

    def test_corrupt_line_is_skipped_not_fatal(self):
        clog = CommandLog(self.path)
        clog.intent("run", actor="owner")
        with self.path.open("a") as fh:
            fh.write("this is not json\n")
        # still readable; the good line survives
        self.assertEqual(len(clog.entries()), 1)
        # and the good line is valid json
        self.assertTrue(all(isinstance(e, dict) for e in clog.entries()))


if __name__ == "__main__":
    unittest.main()
