"""MARIONETTE STEALTH DRIVER — COMPATIBILITY SHIM & PUBLIC ENTRYPOINT.

Berkas ini menyediakan backward-compatibility shim untuk kode atau skrip
yang mengimpor langsung dari root `marionette_driver.py`, sambil mengekspor
seluruh fitur modern dari modul paket `firefox_stealth`.
"""

from firefox_stealth.browser import StealthBrowser, get_firefox_executable
from firefox_stealth.driver import MarionetteDriver
from firefox_stealth.exceptions import (
    BrowserProcessError,
    MarionetteConnectionError,
    MarionetteException,
    MarionetteProtocolError,
    MarionetteTimeoutError,
    NoSuchElementException,
    ScriptExecutionError,
)

__all__ = [
    "MarionetteDriver",
    "StealthBrowser",
    "get_firefox_executable",
    "MarionetteException",
    "MarionetteConnectionError",
    "MarionetteTimeoutError",
    "MarionetteProtocolError",
    "NoSuchElementException",
    "ScriptExecutionError",
    "BrowserProcessError",
]
