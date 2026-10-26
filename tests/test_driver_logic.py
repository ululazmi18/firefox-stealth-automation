"""Unit tests for driver framing, error translation, and browser discovery."""

import json
import unittest
from pathlib import Path
from unittest.mock import MagicMock

from firefox_stealth.browser import StealthBrowser, get_firefox_executable
from firefox_stealth.driver import MarionetteDriver
from firefox_stealth.exceptions import (
    MarionetteConnectionError,
    NoSuchElementException,
    ScriptExecutionError,
)


class TestDriverLogic(unittest.TestCase):
    def test_init_state(self):
        driver = MarionetteDriver(host="127.0.0.1", port=2828)
        self.assertEqual(driver.host, "127.0.0.1")
        self.assertEqual(driver.port, 2828)
        self.assertIsNone(driver.sock)
        self.assertIsNone(driver.session_id)

    def test_send_without_connect_raises(self):
        driver = MarionetteDriver()
        with self.assertRaises(MarionetteConnectionError):
            driver.send("WebDriver:Navigate", {"url": "https://example.com"})

    def test_error_translation_element_not_found(self):
        driver = MarionetteDriver()
        mock_sock = MagicMock()

        # Mocking an error response from Marionette: [type, msg_id, error, result]
        payload = json.dumps([1, 1, {"error": "no such element", "message": "Unable to locate element: #nonexistent"}, None])
        raw_msg = f"{len(payload)}:{payload}".encode("utf-8")

        # Mock recv to return length prefix then colon then payload
        def fake_recv(n):
            nonlocal raw_msg
            if not raw_msg:
                return b""
            chunk = raw_msg[:n]
            raw_msg = raw_msg[n:]
            return chunk

        mock_sock.recv.side_effect = fake_recv
        driver.sock = mock_sock

        with self.assertRaises(NoSuchElementException) as ctx:
            driver.find_element("css selector", "#nonexistent")
        self.assertIn("Unable to locate element", str(ctx.exception))

    def test_error_translation_script_error(self):
        driver = MarionetteDriver()
        mock_sock = MagicMock()

        payload = json.dumps([1, 1, {"error": "javascript error", "message": "ReferenceError: foo is not defined"}, None])
        raw_msg = f"{len(payload)}:{payload}".encode("utf-8")

        def fake_recv(n):
            nonlocal raw_msg
            if not raw_msg:
                return b""
            chunk = raw_msg[:n]
            raw_msg = raw_msg[n:]
            return chunk

        mock_sock.recv.side_effect = fake_recv
        driver.sock = mock_sock

        with self.assertRaises(ScriptExecutionError) as ctx:
            driver.execute_script("return foo();")
        self.assertIn("ReferenceError: foo is not defined", str(ctx.exception))

    def test_browser_config(self):
        browser = StealthBrowser(port=2929, headless=True)
        self.assertEqual(browser.port, 2929)
        self.assertTrue(browser.headless)
        self.assertIsNone(browser.process)


if __name__ == "__main__":
    unittest.main()
