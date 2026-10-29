"""Unit tests for project-isolated profile management and session persistence."""

import os
import tempfile
import unittest
from pathlib import Path

from firefox_stealth.profile import (
    clean_profile_locks,
    get_profile_summary,
    read_profile_cookies,
    resolve_profile_dir,
    save_playwright_cookies_to_firefox,
    setup_clean_profile,
)


class TestProfileIsolation(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.workspace = Path(self.temp_dir.name)

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_resolve_profile_dir_explicit(self):
        custom = self.workspace / "custom_profile"
        resolved = resolve_profile_dir(profile_dir=custom)
        self.assertEqual(resolved, custom.resolve())

    def test_resolve_profile_dir_workspace(self):
        resolved = resolve_profile_dir(workspace_dir=self.workspace)
        expected = (self.workspace / "browser_profile").resolve()
        self.assertEqual(resolved, expected)

    def test_resolve_profile_dir_env(self):
        env_path = str(self.workspace / "env_profile")
        old_env = os.environ.get("BROWSER_PROFILE")
        try:
            os.environ["BROWSER_PROFILE"] = env_path
            resolved = resolve_profile_dir()
            self.assertEqual(resolved, Path(env_path).resolve())
        finally:
            if old_env is not None:
                os.environ["BROWSER_PROFILE"] = old_env
            else:
                os.environ.pop("BROWSER_PROFILE", None)

    def test_clean_profile_locks(self):
        p = self.workspace / "test_prof"
        p.mkdir(parents=True)
        lock_file = p / "parent.lock"

        # 1. No lockfile -> returns False
        self.assertFalse(clean_profile_locks(p))

        # 2. Orphaned lockfile -> returns True and removes file
        lock_file.write_text("test lock")
        self.assertTrue(lock_file.exists())
        self.assertTrue(clean_profile_locks(p))
        self.assertFalse(lock_file.exists())

    def test_setup_clean_profile_custom_port(self):
        p = self.workspace / "port_prof"
        setup_clean_profile(p, port=2929)
        user_js = p / "user.js"
        self.assertTrue(user_js.exists())
        content = user_js.read_text(encoding="utf-8")
        self.assertIn('user_pref("marionette.port", 2929);', content)

    def test_save_playwright_cookies_and_summary(self):
        p = self.workspace / "pw_prof"
        p.mkdir(parents=True)

        pw_cookies = [
            {
                "name": "OSID",
                "value": "secret_token_abc",
                "domain": ".google.com",
                "path": "/",
                "expires": 1800000000,
                "secure": True,
                "httpOnly": True,
                "sameSite": "None",
            },
            {
                "name": "session_id",
                "value": "sess_xyz",
                "domain": "example.com",
                "path": "/app",
                "expires": -1,
                "secure": False,
                "httpOnly": False,
                "sameSite": "Lax",
            },
        ]

        saved = save_playwright_cookies_to_firefox(pw_cookies, profile_dir=p)
        self.assertEqual(saved, 2)

        summary = get_profile_summary(p)
        self.assertTrue(summary["exists"])
        self.assertTrue(summary["has_cookies"])
        self.assertEqual(summary["cookie_count"], 2)
        self.assertTrue(any("google" in d for d in summary["domains"]))

        read = read_profile_cookies(p)
        self.assertEqual(len(read), 2)


if __name__ == "__main__":
    unittest.main()
