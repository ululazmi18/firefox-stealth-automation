"""FIREFOX STEALTH AUTOMATION — UNDETECTED GECKO AUTOMATION SUITE.

Framework otomasi peramban mandiri (standalone) berbasis Mozilla Firefox Portable Edition
yang dikeraskan (hardened) secara native untuk meminimalkan sinyal deteksi otomasi dan fingerprinting,
dengan dukungan isolasi profil privat lokal per proyek untuk login akun aman.
"""

from firefox_stealth.auth import (
    automated_google_login,
    launch_interactive_login,
    verify_session_headless,
)
from firefox_stealth.browser import (
    StealthBrowser,
    get_default_workspace,
    get_firefox_executable,
)
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
    clean_profile_locks,
    get_profile_summary,
    read_profile_cookies,
    resolve_profile_dir,
    save_cookies_to_profile,
    save_playwright_cookies_to_firefox,
    setup_clean_profile,
)

__version__ = "1.1.0"
__author__ = "Ulul Azmi"

__all__ = [
    # Peramban & Driver
    "MarionetteDriver",
    "StealthBrowser",
    "get_firefox_executable",
    "get_default_workspace",
    # Manajemen Profil & Isolasi Sesi
    "resolve_profile_dir",
    "setup_clean_profile",
    "clean_profile_locks",
    "read_profile_cookies",
    "save_cookies_to_profile",
    "save_playwright_cookies_to_firefox",
    "get_profile_summary",
    # Autentikasi Mandiri
    "automated_google_login",
    "verify_session_headless",
    "launch_interactive_login",
    # Pengecualian
    "MarionetteException",
    "MarionetteConnectionError",
    "MarionetteTimeoutError",
    "MarionetteProtocolError",
    "NoSuchElementException",
    "ScriptExecutionError",
    "BrowserProcessError",
]
