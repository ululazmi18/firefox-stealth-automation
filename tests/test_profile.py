"""Unit tests for profile initialization and cookie management."""

import tempfile
import unittest
from pathlib import Path

from firefox_stealth.profile import (
    read_profile_cookies,
    save_cookies_to_profile,
    setup_clean_profile,
)


class TestProfile(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.profile_dir = Path(self.temp_dir.name)

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_setup_clean_profile(self):
        p = setup_clean_profile(self.profile_dir)
        user_js = p / "user.js"
        self.assertTrue(user_js.exists())
        content = user_js.read_text(encoding="utf-8")
        self.assertIn('user_pref("marionette.enabled", true);', content)
        self.assertIn('user_pref("dom.webdriver.enabled", false);', content)
        self.assertIn('user_pref("media.peerconnection.ice.no_host", true);', content)

    def test_cookie_read_write(self):
        cookies_to_insert = [
            {
                "name": "SID",
                "value": "sample_sid_token_123",
                "domain": ".google.com",
                "path": "/",
                "secure": True,
                "httpOnly": False,
            },
            {
                "name": "LOGIN_INFO",
                "value": "youtube_login_token_456",
                "domain": ".youtube.com",
                "path": "/",
                "secure": True,
                "httpOnly": True,
            },
        ]
        inserted = save_cookies_to_profile(cookies_to_insert, self.profile_dir)
        self.assertEqual(inserted, 2)

        read_all = read_profile_cookies(self.profile_dir)
        self.assertEqual(len(read_all), 2)

        read_yt = read_profile_cookies(self.profile_dir, domain_filter="youtube")
        self.assertEqual(len(read_yt), 1)
        self.assertEqual(read_yt[0]["name"], "LOGIN_INFO")
        self.assertEqual(read_yt[0]["value"], "youtube_login_token_456")


if __name__ == "__main__":
    unittest.main()
