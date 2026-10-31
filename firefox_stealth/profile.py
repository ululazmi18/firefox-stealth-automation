"""PROFILE HARDENING & ISOLATED COOKIE VAULT — FIREFOX STEALTH AUTOMATION.

Modul ini bertanggung jawab menginisialisasi setelan profil peramban terisolasi,
menerapkan hardening privasi dan anti-fingerprinting di user.js, membersihkan lockfile yatim,
serta mengelola pertukaran token cookie di cookies.sqlite secara atomik dan aman dari database lock.
Menjamin setiap proyek memiliki profil privat lokal yang mandiri dan tidak bercampur.
"""

import os
import sqlite3
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

HARDENED_USER_PREFS = """// KONFIGURASI OTOMASI MARIONETTE BASELINE
user_pref("marionette.enabled", true);
user_pref("marionette.port", 2828);
user_pref("dom.webdriver.enabled", false);
user_pref("toolkit.telemetry.enabled", false);
user_pref("toolkit.telemetry.reportingpolicy.firstRun", false);
user_pref("browser.sessionstore.resume_from_crash", false);

// ⚡ TUNING EFISIENSI RAM & KECEPATAN (ZERO-WASTE RESOURCE)
user_pref("accessibility.force_disabled", 1);               // Hemat 50-80MB RAM (matikan accessibility engine)
user_pref("dom.ipc.processCount", 1);                       // Hemat 150MB+ RAM (batasi 1 content process untuk otomasi)
user_pref("browser.cache.disk.enable", false);              // Matikan cache disk (minimalkan write I/O di Windows)
user_pref("browser.cache.memory.enable", true);
user_pref("browser.cache.memory.capacity", 32768);           // Batasi cache RAM 32MB (bukan ratusan MB)
user_pref("image.mem.decodeondraw", true);                  // Hanya decode gambar saat dirender
user_pref("browser.startup.homepage", "about:blank");       // Startup instan tanpa load feed
user_pref("browser.newtabpage.enabled", false);
user_pref("browser.safebrowsing.malware.enabled", false);   // Cegah download background DB besar
user_pref("browser.safebrowsing.phishing.enabled", false);
user_pref("extensions.pocket.enabled", false);
user_pref("network.captive-portal-service.enabled", false);
user_pref("app.update.auto", false);
user_pref("app.update.enabled", false);
user_pref("datareporting.healthreport.uploadEnabled", false);
user_pref("network.http.max-persistent-connections-per-server", 10);

// HARDENING WEBRTC & PRIVASI JARINGAN
user_pref("media.peerconnection.enabled", true);
user_pref("media.peerconnection.ice.no_host", true);
user_pref("media.peerconnection.ice.default_address_only", true);

// PERLINDUNGAN POPUP & DOWNLOAD
user_pref("browser.download.panel.shown", false);
user_pref("browser.helperApps.neverAsk.saveToDisk", "application/octet-stream");
"""


def resolve_profile_dir(
    profile_dir: Optional[Union[Path, str]] = None,
    workspace_dir: Optional[Union[Path, str]] = None,
) -> Path:
    """Menyelesaikan direktori profil peramban terisolasi untuk proyek aktif.

    Prioritas resolusi:
    1. Argumen `profile_dir` eksplisit.
    2. Variabel lingkungan BROWSER_PROFILE.
    3. `workspace_dir / 'browser_profile'` jika direktori workspace diberikan.
    4. `Path.cwd() / 'browser_profile'` (direktori proyek aktif pemanggil).

    Dengan strategi ini, setiap proyek memiliki folder profil sendiri yang terisolasi
    dan tidak saling mencemari sesi/login akun dengan proyek lain di direktori mana pun.

    Args:
        profile_dir: Jalur profil yang ditentukan secara manual.
        workspace_dir: Direktori root proyek pemanggil.

    Returns:
        Path: Jalur absolut ke direktori profil terisolasi.
    """
    if profile_dir:
        return Path(profile_dir).resolve()

    env_profile = os.environ.get("BROWSER_PROFILE")
    if env_profile:
        return Path(env_profile).resolve()

    if workspace_dir:
        return (Path(workspace_dir).resolve() / "browser_profile")

    return (Path.cwd().resolve() / "browser_profile")


def clean_profile_locks(profile_dir: Union[Path, str]) -> bool:
    """Memeriksa dan membersihkan berkas lock yatim (parent.lock) jika peramban tidak aktif.

    Jika file 'parent.lock' ada tetapi dapat dibuka dalam mode append, berarti berkas
    tersebut adalah lock yatim dari sesi sebelumnya yang crash atau ditutup paksa.
    Fungsi ini melakukan self-healing dengan menghapus lockfile tersebut agar sesi baru
    dapat dimulai tanpa galat 'Firefox is already running'.

    Args:
        profile_dir: Direktori profil peramban sasaran.

    Returns:
        bool: True jika lock yatim berhasil dibersihkan, False jika tidak ada lock atau terkunci aktif.
    """
    p = Path(profile_dir)
    lock_file = p / "parent.lock"
    if not lock_file.exists():
        return False

    try:
        with open(lock_file, "a"):
            pass
        lock_file.unlink(missing_ok=True)
        return True
    except (OSError, PermissionError):
        # Sedang digunakan proses Firefox aktif
        return False


def setup_clean_profile(profile_dir: Union[Path, str], port: int = 2828) -> Path:
    """Menginisialisasi direktori profil peramban dengan konfigurasi user.js yang dikeraskan.

    Args:
        profile_dir: Direktori profil peramban sasaran.
        port: Port Marionette yang akan dibuka (default: 2828).

    Returns:
        Path: Direktori profil yang siap digunakan.
    """
    p = Path(profile_dir).resolve()
    p.mkdir(parents=True, exist_ok=True)
    clean_profile_locks(p)

    user_js = p / "user.js"
    prefs = HARDENED_USER_PREFS.replace(
        'user_pref("marionette.port", 2828);',
        f'user_pref("marionette.port", {port});',
    )
    if not user_js.exists():
        user_js.write_text(prefs, encoding="utf-8")
    else:
        # Self-updating: Tambahkan tuning RAM jika profil lama belum memiliki pref terbaru
        content = user_js.read_text(encoding="utf-8", errors="ignore")
        if "accessibility.force_disabled" not in content:
            user_js.write_text(prefs, encoding="utf-8")
    return p


def read_profile_cookies(profile_dir: Union[Path, str], domain_filter: Optional[str] = None) -> List[Dict[str, Any]]:
    """Membaca daftar token cookie yang tersimpan di cookies.sqlite profil peramban.

    Args:
        profile_dir: Direktori profil peramban.
        domain_filter: Filter host (misal 'google' atau 'youtube').

    Returns:
        List[Dict[str, Any]]: Kumpulan kamus atribut cookie.
    """
    p = Path(profile_dir)
    db_path = p / "cookies.sqlite"
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


def save_cookies_to_profile(cookies: List[Dict[str, Any]], profile_dir: Union[Path, str], retries: int = 5) -> int:
    """Menyimpan sekumpulan cookie ke basis data moz_cookies dengan perlindungan lock defensif.

    Args:
        cookies: Daftar dictionary cookie (format Playwright/Selenium/W3C).
        profile_dir: Direktori profil peramban sasaran.
        retries: Jumlah percobaan ulang jika database sedang terkunci (locked).

    Returns:
        int: Jumlah baris cookie yang berhasil disimpan/diperbarui.
    """
    p = Path(profile_dir)
    p.mkdir(parents=True, exist_ok=True)
    db_path = p / "cookies.sqlite"

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
            try:
                cur.execute("PRAGMA wal_checkpoint(FULL);")
            except Exception:
                pass
            conn.close()
            return inserted_count
        except sqlite3.OperationalError:
            if attempt < retries - 1:
                time.sleep(0.5)
            else:
                raise
    return 0


def save_playwright_cookies_to_firefox(
    cookies: List[Dict[str, Any]],
    profile_dir: Union[Path, str],
    clear_domains: Optional[List[str]] = None,
) -> int:
    """Menyimpan daftar cookies Playwright ke cookies.sqlite profil Firefox Portable lokal.

    Menegakkan standar Firefox Gecko 115+:
    - Masa kedaluwarsa format mikrodetik/detik sesuai schema.
    - schemeMap = 2 (HTTPS bitmask).
    - sameSite = 256 (SAMESITE_UNSET) untuk kompatibilitas domain web modern & Google.
    - Checkpoint SQLite WAL langsung ke file database utama.

    Args:
        cookies: Daftar dictionary cookie dari Playwright context.cookies().
        profile_dir: Direktori profil Firefox sasaran.
        clear_domains: Daftar domain yang akan dibersihkan sebelum injeksi (opsional).

    Returns:
        int: Jumlah cookie yang berhasil disimpan ke database.
    """
    p = Path(profile_dir)
    p.mkdir(parents=True, exist_ok=True)
    db_path = p / "cookies.sqlite"

    conn = sqlite3.connect(db_path, timeout=10.0)
    cur = conn.cursor()

    # Pastikan tabel moz_cookies ada
    if not cur.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='moz_cookies'"
    ).fetchone():
        cur.execute(
            """
            CREATE TABLE moz_cookies (
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
                isPartitionedAttributeSet INTEGER DEFAULT 0,
                updateTime INTEGER,
                CONSTRAINT moz_uniqueid UNIQUE (name, host, path, originAttributes)
            )
            """
        )
        conn.commit()

    if clear_domains:
        for dom in clear_domains:
            cur.execute("DELETE FROM moz_cookies WHERE host LIKE ?", (f"%{dom}%",))
        conn.commit()

    cols = [c[1] for c in cur.execute("PRAGMA table_info(moz_cookies)").fetchall()]
    has_same_site = "sameSite" in cols
    has_scheme_map = "schemeMap" in cols
    has_update_time = "updateTime" in cols

    now = int(time.time())
    now_us = int(time.time() * 1_000_000)
    saved_count = 0

    for c in cookies:
        name = c["name"]
        value = c["value"]
        domain = c["domain"]
        path = c.get("path", "/")
        expires = int(c.get("expires", 0))
        if expires <= 0:
            expires = now + (365 * 24 * 3600)

        is_secure = 1 if c.get("secure", False) else 0
        is_http_only = 1 if c.get("httpOnly", False) else 0

        # Gecko sameSite mapping
        same_site_str = c.get("sameSite", "None").capitalize()
        same_site_val = 0
        if same_site_str == "Strict":
            same_site_val = 2
        elif same_site_str == "Lax":
            same_site_val = 1
        elif same_site_str == "None":
            same_site_val = 256  # SAMESITE_UNSET Gecko

        scheme_map_val = 2 if is_secure else 1

        fields = ["originAttributes", "name", "value", "host", "path", "expiry", "lastAccessed", "creationTime", "isSecure", "isHttpOnly"]
        values = ["", name, value, domain, path, expires, now_us, now_us, is_secure, is_http_only]

        if has_same_site:
            fields.append("sameSite")
            values.append(same_site_val)
        if has_scheme_map:
            fields.append("schemeMap")
            values.append(scheme_map_val)
        if has_update_time:
            fields.append("updateTime")
            values.append(now_us)

        placeholders = ", ".join(["?"] * len(values))
        cols_str = ", ".join(fields)
        update_str = ", ".join([f"{f}=excluded.{f}" for f in fields if f not in ("originAttributes", "name", "host", "path")])

        sql = f"""
            INSERT INTO moz_cookies ({cols_str})
            VALUES ({placeholders})
            ON CONFLICT(name, host, path, originAttributes) DO UPDATE SET {update_str}
        """
        cur.execute(sql, values)
        saved_count += 1

    conn.commit()
    try:
        cur.execute("PRAGMA wal_checkpoint(FULL);")
    except Exception:
        pass
    conn.close()
    return saved_count


def get_profile_summary(profile_dir: Union[Path, str]) -> Dict[str, Any]:
    """Mendapatkan ringkasan status profil (jumlah cookie, domain tersimpan, ukuran).

    Args:
        profile_dir: Direktori profil peramban sasaran.

    Returns:
        Dict[str, Any]: Kamus metadata status profil.
    """
    p = Path(profile_dir)
    cookies_db = p / "cookies.sqlite"
    summary: Dict[str, Any] = {
        "profile_dir": str(p.resolve()),
        "exists": p.exists(),
        "has_user_js": (p / "user.js").exists(),
        "has_cookies": cookies_db.exists(),
        "cookie_count": 0,
        "domains": [],
        "locked": (p / "parent.lock").exists(),
    }
    if cookies_db.exists():
        try:
            conn = sqlite3.connect(f"file:{cookies_db}?mode=ro", uri=True)
            cur = conn.cursor()
            cnt = cur.execute("SELECT COUNT(*) FROM moz_cookies").fetchone()[0]
            domains = [r[0] for r in cur.execute("SELECT DISTINCT host FROM moz_cookies LIMIT 25").fetchall()]
            summary["cookie_count"] = cnt
            summary["domains"] = domains
            conn.close()
        except Exception:
            pass
    return summary
