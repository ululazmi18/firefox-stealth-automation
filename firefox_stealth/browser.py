"""STEALTH BROWSER PROCESS MANAGER & HIGH-LEVEL FACADE.

Modul ini mengelola siklus hidup proses biner Firefox Portable, memastikan
port Marionette aktif, menangani eksekusi headless/headful, serta menyediakan
antarmuka tingkat tinggi (High-Level Facade) dan context manager untuk otomasi.
"""

import os
import subprocess
import time
from pathlib import Path
from typing import Any, List, Optional

from firefox_stealth.driver import MarionetteDriver
from firefox_stealth.exceptions import BrowserProcessError, MarionetteTimeoutError


def get_default_workspace() -> Path:
    """Mendapatkan direktori root repositori secara andal."""
    return Path(__file__).resolve().parent.parent


def get_firefox_executable(portable_dir: Optional[Path] = None) -> Optional[Path]:
    """Mencari jalur berkas firefox.exe portable yang tersedia di sistem.

    Args:
        portable_dir (Path | None): Direktori instalasi lokal firefox_portable.

    Returns:
        Path | None: Jalur absolut firefox.exe jika ditemukan, atau None.
    """
    root = get_default_workspace()
    target_dir = portable_dir or (root / "firefox_portable")
    candidates = [
        target_dir / "App" / "Firefox64" / "firefox.exe",
        target_dir / "App" / "Firefox" / "firefox.exe",
        target_dir / "core" / "firefox.exe",
        target_dir / "firefox.exe",
        # Lokasi portable apps universal di Drive D:
        Path(r"D:\FirefoxPortable\App\Firefox64\firefox.exe"),
        Path(r"D:\FirefoxPortable\firefox.exe"),
    ]
    for path in candidates:
        if path.exists() and path.is_file():
            return path.resolve()
    return None


class StealthBrowser:
    """Manajer proses peramban Firefox Stealth berbasis Marionette.

    Menangani siklus hidup lengkap subprocess Firefox Portable, pembuatan profil,
    koneksi soket TCP otomatis, penutupan anggun (graceful termination), serta
    menyediakan konteks eksekusi otomatis (context manager).

    Contoh Penggunaan:
        >>> with StealthBrowser(headless=True) as browser:
        ...     browser.driver.navigate("https://bot.sannysoft.com")
        ...     print(browser.driver.title)
    """

    def __init__(
        self,
        firefox_bin: Optional[Path] = None,
        profile_dir: Optional[Path] = None,
        port: int = 2828,
        headless: bool = True,
        extra_args: Optional[List[str]] = None,
    ) -> None:
        """Inisialisasi manajer proses browser.

        Args:
            firefox_bin: Jalur biner firefox.exe. Jika None, dideteksi otomatis.
            profile_dir: Jalur direktori profil browser. Jika None, gunakan browser_profile lokal.
            port: Port Marionette (default 2828).
            headless: Jalankan tanpa antarmuka grafis (default True).
            extra_args: Argumen baris perintah tambahan untuk Firefox.
        """
        self.root_dir = get_default_workspace()
        self.firefox_bin = Path(firefox_bin) if firefox_bin else get_firefox_executable()
        self.profile_dir = Path(profile_dir) if profile_dir else (self.root_dir / "browser_profile")
        self.port = port
        self.headless = headless
        self.extra_args = extra_args or []

        self.process: Optional[subprocess.Popen] = None
        self._driver: Optional[MarionetteDriver] = None

    def __enter__(self) -> "StealthBrowser":
        """Memulai peramban otomatis saat masuk blok context manager."""
        self.start()
        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        """Menghentikan dan membersihkan peramban secara aman."""
        self.stop()

    @property
    def driver(self) -> MarionetteDriver:
        """Mengakses instansi MarionetteDriver yang terhubung."""
        if not self._driver or not self._driver.sock:
            raise BrowserProcessError("Driver belum terhubung. Jalankan start() terlebih dahulu.")
        return self._driver

    def start(self, startup_timeout: float = 25.0) -> MarionetteDriver:
        """Meluncurkan proses Firefox Portable dan menghubungkan Marionette driver.

        Args:
            startup_timeout: Waktu tunggu maksimal peramban siap dalam detik.

        Returns:
            MarionetteDriver: Instansi driver yang sudah terotentikasi dan siap dipakai.

        Raises:
            BrowserProcessError: Jika biner tidak ditemukan atau proses gagal meluncur.
            MarionetteTimeoutError: Jika port Marionette tidak terbuka dalam batas waktu.
        """
        if not self.firefox_bin or not self.firefox_bin.exists():
            raise BrowserProcessError(
                f"Biner Firefox tidak ditemukan di: {self.firefox_bin}. "
                "Jalankan 'python setup_browser.py' terlebih dahulu."
            )

        self.profile_dir.mkdir(parents=True, exist_ok=True)

        cmd = [
            str(self.firefox_bin),
            "-no-remote",
            "-marionette",
            "-profile",
            str(self.profile_dir),
        ]
        if self.headless:
            cmd.append("-headless")
        cmd.extend(self.extra_args)

        env = os.environ.copy()
        try:
            self.process = subprocess.Popen(
                cmd,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                env=env,
            )
        except OSError as exc:
            raise BrowserProcessError(f"Gagal mengeksekusi biner peramban: {exc}") from exc

        # Tunggu pembukaan port Marionette
        self._driver = MarionetteDriver(host="127.0.0.1", port=self.port)
        start_time = time.time()
        while time.time() - start_time < startup_timeout:
            if self.process.poll() is not None:
                raise BrowserProcessError(
                    f"Proses Firefox berhenti sebelum siap (kode keluar: {self.process.returncode})."
                )
            if self._driver.is_port_open(timeout=0.4):
                break
            time.sleep(0.3)
        else:
            self.stop()
            raise MarionetteTimeoutError(
                f"Port Marionette {self.port} tidak merespons setelah {startup_timeout} detik."
            )

        # Buka sesi
        self._driver.connect(timeout=startup_timeout)
        return self._driver

    def stop(self) -> None:
        """Menghentikan sesi driver dan mematikan subprocess peramban secara aman."""
        if self._driver:
            try:
                self._driver.close()
            except Exception:
                pass
            self._driver = None

        if self.process:
            try:
                self.process.terminate()
                self.process.wait(timeout=4.0)
            except Exception:
                try:
                    self.process.kill()
                except Exception:
                    pass
            self.process = None
