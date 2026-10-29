"""Unit tests for firefox-stealth CLI commands and argument parser."""

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from firefox_stealth.cli import main


class TestCLI(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.profile_dir = Path(self.temp_dir.name) / "test_cli_profile"

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_cli_help(self):
        with self.assertRaises(SystemExit) as cm:
            main(["--help"])
        self.assertEqual(cm.exception.code, 0)

    def test_cli_version(self):
        with self.assertRaises(SystemExit) as cm:
            main(["--version"])
        self.assertEqual(cm.exception.code, 0)

    def test_cli_profile_init_and_info(self):
        # 1. Init profil via CLI
        code = main(["profile", "--profile-dir", str(self.profile_dir), "--action", "init"])
        self.assertEqual(code, 0)
        self.assertTrue((self.profile_dir / "user.js").exists())

        # 2. Info profil via CLI
        code_info = main(["profile", "--profile-dir", str(self.profile_dir), "--action", "info"])
        self.assertEqual(code_info, 0)

        # 3. Clean profil via CLI
        code_clean = main(["profile", "--profile-dir", str(self.profile_dir), "--action", "clean"])
        self.assertEqual(code_clean, 0)

    def test_cli_no_args_shows_overview(self):
        code = main([])
        self.assertEqual(code, 0)


if __name__ == "__main__":
    unittest.main()
