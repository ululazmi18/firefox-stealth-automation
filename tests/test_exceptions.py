"""Unit tests for firefox_stealth custom exceptions."""

import unittest
from firefox_stealth.exceptions import (
    BrowserProcessError,
    MarionetteConnectionError,
    MarionetteException,
    MarionetteProtocolError,
    MarionetteTimeoutError,
    NoSuchElementException,
    ScriptExecutionError,
)


class TestExceptions(unittest.TestCase):
    def test_hierarchy(self):
        self.assertTrue(issubclass(MarionetteConnectionError, MarionetteException))
        self.assertTrue(issubclass(MarionetteTimeoutError, MarionetteException))
        self.assertTrue(issubclass(MarionetteProtocolError, MarionetteException))
        self.assertTrue(issubclass(NoSuchElementException, MarionetteProtocolError))
        self.assertTrue(issubclass(ScriptExecutionError, MarionetteProtocolError))
        self.assertTrue(issubclass(BrowserProcessError, MarionetteException))

    def test_exception_formatting(self):
        exc = NoSuchElementException("Element '#foo' not found", details={"error": "no such element"})
        self.assertIn("Element '#foo' not found", str(exc))
        self.assertIn("no such element", str(exc))
        self.assertEqual(exc.details["error"], "no such element")


if __name__ == "__main__":
    unittest.main()
