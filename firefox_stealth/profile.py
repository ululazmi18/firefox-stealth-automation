"""PROFILE HARDENING & COOKIE VAULT — FIREFOX STEALTH AUTOMATION.

Modul ini bertanggung jawab menginisialisasi setelan profil peramban terisolasi,
menerapkan hardening privasi dan anti-fingerprinting di user.js, serta mengelola
pertukaran token cookie di cookies.sqlite secara atomik dan aman dari database lock.
"""

import sqlite3
import time
from pathlib import Path
from typing import Any, Dict, List, Optional


HARDENED_USER_PREFS = """// KONFIGURASI OTOMASI MARIONETTE BASELINE
user_pref("marionette.enabled", true);
user_pref("marionette.port", 2828);
user_pref("dom.webdriver.enabled", false);
user_pref("toolkit.telemetry.enabled", false);
user_pref("toolkit.telemetry.reportingpolicy.firstRun", false);
user_pref("browser.sessionstore.resume_from_crash", false);

// HARDENING WEBRTC & PRIVASI JARINGAN
user_pref("media.peerconnection.enabled", true);
user_pref("media.peerconnection.ice.no_host", true);
user_pref("media.peerconnection.ice.default_address_only", true);

// PERLINDUNGAN POPUP & DOWNLOAD
user_pref("browser.download.panel.shown", false);
user_pref("browser.helperApps.neverAsk.saveToDisk", "application/octet-stream");
"""


def setup_clean_profile(profile_dir: Path) -> Path:
    """Menginisialisasi direktori profil peramban dengan konfigurasi user.js yang dikeraskan.

    Args:
        profile_dir (Path): Direktori profil peramban sasaran.

    Returns:
        Path: Direktori profil yang siap digunakan.
    """
    profile_dir.mkdir(parents=True, exist_ok=True)
    user_js = profile_dir / "user.js"
    if not user_js.exists():
        user_js.write_text(HARDENED_USER_PREFS, encoding="utf-8")
    return profile_dir


def read_profile_cookies(profile_dir: Path, domain_filter: Optional[str] = None) -> List[Dict[str, Any]]:
    """Membaca daftar token cookie yang tersimpan di cookies.sqlite profil peramban.

    Args:
        profile_dir: Direktori profil peramban.
        domain_filter: Filter host (misal 'google' atau 'youtube').

    Returns:
        List[Dict[str, Any]]: Kumpulan kamus atribut cookie.
    """
    db_path = profile_dir / "cookies.sqlite"
    if not db_path.exists():
        return []

    # Membaca dengan mode URI read-only untuk mencegah bentrok lock saat browser aktif
    conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    cur = conn.cursor()

    query = "SELECT host, name, value, path, expiry, isSecure, isHttpOnly, sameSite FROM moz_cookies"
    params: List[Any] = []
    if domain_filter:
        query += " WHERE host LIKE ?"
        params.append(f"%{domain_filter}%")

    try:
        rows = cur.execute(query, params).fetchall()
        cookies = [
            {
                "domain": r[0],
                "name": r[1],
                "value": r[2],
                "path": r[3],
                "expires": r[4],
                "secure": bool(r[5]),
                "httpOnly": bool(r[6]),
                "sameSite": r[7],
            }
            for r in rows
        ]
        return cookies
    finally:
        conn.close()


def save_cookies_to_profile(cookies: List[Dict[str, Any]], profile_dir: Path, retries: int = 5) -> int:
    """Menyimpan sekumpulan cookie ke basis data moz_cookies dengan perlindungan lock defensif.

    Args:
        cookies: Daftar dictionary cookie (format Playwright/Selenium/W3C).
        profile_dir: Direktori profil peramban sasaran.
        retries: Jumlah percobaan ulang jika database sedang terkunci (locked).

    Returns:
        int: Jumlah baris cookie yang berhasil disimpan/diperbarui.
    """
    profile_dir.mkdir(parents=True, exist_ok=True)
    db_path = profile_dir / "cookies.sqlite"

    for attempt in range(retries):
        try:
            conn = sqlite3.connect(db_path, timeout=10.0)
            cur = conn.cursor()

            # Pastikan tabel moz_cookies ada
            cur.execute("""
                CREATE TABLE IF NOT EXISTS moz_cookies (
                    id INTEGER PRIMARY KEY,
                    originAttributes TEXT NOT NULL DEFAULT '',
                    name TEXT,
                    value TEXT,
                    host TEXT,
                    path TEXT,
                    expiry INTEGER,
                    lastAccessed INTEGER,
                    creationTime INTEGER,
                    isSecure INTEGER,
                    isHttpOnly INTEGER,
                    inBrowserElement INTEGER DEFAULT 0,
                    sameSite INTEGER DEFAULT 0,
                    rawSameSite INTEGER DEFAULT 0,
                    schemeMap INTEGER DEFAULT 0,
                    CONSTRAINT moz_uniqueid UNIQUE (name, host, path, originAttributes)
                );
            """)

            now_us = int(time.time() * 1_000_000)
            inserted_count = 0

            for c in cookies:
                name = c.get("name", "")
                val = c.get("value", "")
                domain = c.get("domain", "")
                path = c.get("path", "/")
                exp = int(c.get("expires", 0) or c.get("expiry", 0) or (time.time() + 31536000))
                secure = 1 if c.get("secure") else 0
                http_only = 1 if c.get("httpOnly") else 0

                cur.execute("""
                    INSERT INTO moz_cookies (
                        originAttributes, name, value, host, path,
                        expiry, lastAccessed, creationTime, isSecure, isHttpOnly,
                        sameSite, rawSameSite, schemeMap
                    ) VALUES ('', ?, ?, ?, ?, ?, ?, ?, ?, ?, 0, 0, 0)
                    ON CONFLICT(name, host, path, originAttributes) DO UPDATE SET
                        value=excluded.value,
                        expiry=excluded.expiry,
                        lastAccessed=excluded.lastAccessed,
                        isSecure=excluded.isSecure,
                        isHttpOnly=excluded.isHttpOnly;
                """, (name, val, domain, path, exp, now_us, now_us, secure, http_only))
                inserted_count += 1

            conn.commit()
            conn.close()
            return inserted_count
        except sqlite3.OperationalError:
            if attempt < retries - 1:
                time.sleep(0.5)
            else:
                raise
    return 0
