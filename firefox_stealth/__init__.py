"""FIREFOX STEALTH AUTOMATION — UNDETECTED GECKO AUTOMATION SUITE.

Framework otomasi peramban mandiri (standalone) berbasis Mozilla Firefox Portable Edition
yang dikeraskan (hardened) secara native untuk meminimalkan sinyal deteksi otomasi dan fingerprinting.
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
from firefox_stealth.profile import (
    read_profile_cookies,
    save_cookies_to_profile,
    setup_clean_profile,
)

__version__ = "1.0.0"
__author__ = "Ulul Azmi"

__all__ = [
    "MarionetteDriver",
    "StealthBrowser",
    "get_firefox_executable",
    "setup_clean_profile",
    "read_profile_cookies",
    "save_cookies_to_profile",
    "MarionetteException",
    "MarionetteConnectionError",
    "MarionetteTimeoutError",
    "MarionetteProtocolError",
    "NoSuchElementException",
    "ScriptExecutionError",
    "BrowserProcessError",
]
