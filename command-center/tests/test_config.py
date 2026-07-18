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


if __name__ == "__main__":
    unittest.main()
