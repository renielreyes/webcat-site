import os
import tempfile
import unittest
from pathlib import Path

from ccengine.lock import SingleFlight, Busy


class TestSingleFlight(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.path = Path(self.tmp.name) / "runner.lock"

    def tearDown(self):
        self.tmp.cleanup()

    def test_second_acquire_while_held_is_busy(self):
        held = SingleFlight(self.path)
        held.__enter__()
        try:
            with self.assertRaises(Busy):
                SingleFlight(self.path).__enter__()
        finally:
            held.__exit__(None, None, None)

    def test_reacquire_after_release(self):
        with SingleFlight(self.path):
            pass
        with SingleFlight(self.path):  # must succeed again
            pass

    def test_holder_pid_recorded(self):
        with SingleFlight(self.path) as lock:
            self.assertEqual(lock.holder_pid(), os.getpid())


if __name__ == "__main__":
    unittest.main()
