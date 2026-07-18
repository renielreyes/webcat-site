import tempfile
import unittest
from pathlib import Path

from ccengine import config as config_mod


class TestConfig(unittest.TestCase):
    def test_defaults_load(self):
        cfg = config_mod.load(environ={})
        self.assertEqual(cfg.repo_full, "renielreyes/webcat-site")
        self.assertEqual(cfg.repo_owner, "renielreyes")
        self.assertEqual(cfg.repo_name, "webcat-site")
        self.assertTrue(cfg.live_url.startswith("http"))
        self.assertEqual(cfg.merge_key_path, "")  # no secret path by default

    def test_env_override(self):
        cfg = config_mod.load(environ={"CC_LIVE_URL": "https://example.test"})
        self.assertEqual(cfg.live_url, "https://example.test")

    def test_empty_env_is_ignored(self):
        cfg = config_mod.load(environ={"CC_LIVE_URL": ""})
        self.assertTrue(cfg.live_url.startswith("http"))  # falls back to default

    def test_toml_file_load(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "cc.toml"
            p.write_text('repo_full = "acmeco/acme-site"\nlive_url = "https://acme.test"\n')
            cfg = config_mod.load(config_path=p, environ={})
            self.assertEqual(cfg.repo_full, "acmeco/acme-site")
            self.assertEqual(cfg.repo_owner, "acmeco")
            self.assertEqual(cfg.live_url, "https://acme.test")

    def test_missing_required_raises(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "cc.toml"
            p.write_text('live_url = ""\n')  # blanks a required field
            with self.assertRaises(config_mod.ConfigError):
                config_mod.load(config_path=p, environ={})

    def test_missing_file_raises(self):
        with self.assertRaises(config_mod.ConfigError):
            config_mod.load(config_path="/no/such/cc.toml", environ={})


class TestStateIsolation(unittest.TestCase):
    """Council fix #1: per-project state must be structurally isolated, not shared."""

    def test_default_state_dir_is_backward_compatible(self):
        cfg = config_mod.load(environ={})
        # The default state_dir reproduces the historical ~/.webcat-loop/* paths exactly.
        self.assertEqual(cfg.state_file, "~/.webcat-loop/pending.json")
        self.assertEqual(cfg.stop_file, "~/.webcat-loop/STOP")
        self.assertEqual(cfg.lock_file, "~/.webcat-loop/runner.lock")
        self.assertEqual(cfg.log_file, "~/.webcat-loop/command-log.jsonl")

    def test_runtime_paths_follow_state_dir(self):
        cfg = config_mod.load(environ={"CC_STATE_DIR": "/tmp/projX"})
        self.assertEqual(str(cfg.path("state_file")), "/tmp/projX/pending.json")
        self.assertEqual(str(cfg.path("stop_file")), "/tmp/projX/STOP")
        self.assertEqual(str(cfg.path("lock_file")), "/tmp/projX/runner.lock")
        self.assertEqual(str(cfg.path("log_file")), "/tmp/projX/command-log.jsonl")

    def test_explicit_path_override_still_wins(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "cc.toml"
            p.write_text('state_dir = "/tmp/projY"\nstate_file = "/custom/pending.json"\n')
            cfg = config_mod.load(config_path=p, environ={})
            self.assertEqual(cfg.state_file, "/custom/pending.json")          # explicit pin kept
            self.assertEqual(str(cfg.path("lock_file")), "/tmp/projY/runner.lock")  # others derive

    def test_two_projects_with_distinct_state_dir_are_disjoint(self):
        a = config_mod.load(environ={"CC_REPO_FULL": "o/a", "CC_STATE_DIR": "/tmp/projA"})
        b = config_mod.load(environ={"CC_REPO_FULL": "o/b", "CC_STATE_DIR": "/tmp/projB"})
        for key in ("state_file", "lock_file", "stop_file", "log_file"):
            self.assertNotEqual(str(a.path(key)), str(b.path(key)))
        config_mod.assert_no_collisions([a, b])   # must NOT raise

    def test_collision_lint_catches_shared_state(self):
        # THE COUNCIL'S CHEAPEST DISPROOF: two projects in the minimal shape (repo_full +
        # live_url only, no state_dir) would share ~/.webcat-loop/* — the lint refuses it.
        a = config_mod.load(environ={"CC_REPO_FULL": "o/a"})
        b = config_mod.load(environ={"CC_REPO_FULL": "o/b"})
        with self.assertRaises(config_mod.ConfigError):
            config_mod.assert_no_collisions([a, b])

    def test_same_project_twice_is_not_a_collision(self):
        a = config_mod.load(environ={"CC_REPO_FULL": "o/a", "CC_STATE_DIR": "/tmp/projA"})
        again = config_mod.load(environ={"CC_REPO_FULL": "o/a", "CC_STATE_DIR": "/tmp/projA"})
        config_mod.assert_no_collisions([a, again])   # same label + paths -> fine


class TestDeployKind(unittest.TestCase):
    """Council fix #7: deploy target is an explicit, validated field — no Azure hardcoding."""

    def test_default_is_azure_swa(self):
        self.assertEqual(config_mod.load(environ={}).deploy_kind, "azure_swa")

    def test_none_is_allowed(self):
        self.assertEqual(config_mod.load(environ={"CC_DEPLOY_KIND": "none"}).deploy_kind, "none")

    def test_unknown_kind_refused(self):
        with self.assertRaises(config_mod.ConfigError):
            config_mod.load(environ={"CC_DEPLOY_KIND": "ftp"})


if __name__ == "__main__":
    unittest.main()
