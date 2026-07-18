import tempfile
import unittest
from pathlib import Path

from ccengine import commands, config as config_mod


class TestStopResume(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.sf = Path(self.tmp.name) / "sub" / "STOP"          # nested → tests parent mkdir
        self.cfg = config_mod.load(environ={"CC_STOP_FILE": str(self.sf)})

    def tearDown(self):
        self.tmp.cleanup()

    def test_stop_creates_the_flag(self):
        self.assertFalse(self.sf.exists())
        r = commands.stop(self.cfg)
        self.assertEqual(r.outcome, "ok")
        self.assertTrue(self.sf.exists())

    def test_stop_is_idempotent(self):
        commands.stop(self.cfg)
        r = commands.stop(self.cfg)
        self.assertEqual(r.outcome, "ok")
        self.assertIn("Already paused", r.message)
        self.assertTrue(self.sf.exists())

    def test_resume_clears_the_flag(self):
        commands.stop(self.cfg)
        r = commands.resume(self.cfg)
        self.assertEqual(r.outcome, "ok")
        self.assertFalse(self.sf.exists())

    def test_resume_when_not_paused(self):
        r = commands.resume(self.cfg)
        self.assertEqual(r.outcome, "ok")
        self.assertIn("already running", r.message)


if __name__ == "__main__":
    unittest.main()
