"""STEALTH BROWSER PROCESS MANAGER & HIGH-LEVEL FACADE.

Modul ini mengelola siklus hidup proses biner Firefox Portable, memastikan
port Marionette aktif, menangani eksekusi headless/headful, serta menyediakan
antarmuka tingkat tinggi (High-Level Facade) dan context manager untuk otomasi.
Mendukung resolusi direktori profil privat terisolasi per proyek kerja.
"""

import os
import shutil
import subprocess
import time
from pathlib import Path
from typing import Any, List, Optional, Union

from firefox_stealth.driver import MarionetteDriver
from firefox_stealth.exceptions import BrowserProcessError, MarionetteTimeoutError
from firefox_stealth.profile import clean_profile_locks, resolve_profile_dir, setup_clean_profile


def get_default_workspace() -> Path:
    """Mendapatkan direktori kerja aktif atau root repositori secara andal."""
    return Path.cwd().resolve()


def get_firefox_executable(
    portable_dir: Optional[Union[Path, str]] = None,
    workspace_dir: Optional[Union[Path, str]] = None,
) -> Optional[Path]:
    """Mencari jalur berkas firefox.exe yang tersedia di sistem secara universal.

    Pencarian dilakukan secara bertahap dan defensif:
    1. Variabel lingkungan FIREFOX_BIN (jika ada).
    2. Direktori `portable_dir` eksplisit (jika diberikan).
    3. Folder `firefox_portable` di direktori workspace proyek aktif.
    4. Folder `firefox_portable` di direktori kerja saat ini (`Path.cwd()`).
    5. Folder `firefox_portable` di instalasi paket `firefox-stealth-automation`.
    6. Direktori instalasi Tools universal (`D:/Tools/firefox-stealth-automation/firefox_portable`, dst).
    7. Lokasi portable apps universal di Drive D: (`D:/FirefoxPortable`).
    8. Eksekutabel Firefox di PATH sistem (`shutil.which`).
    9. Direktori standar Program Files Windows.

    Args:
        portable_dir: Direktori instalasi biner lokal yang ingin diprioritaskan.
        workspace_dir: Direktori root proyek pemanggil.

    Returns:
        Path | None: Jalur absolut berkas firefox.exe jika ditemukan, atau None.
    """
    # 1. Environment variable eksplisit
    env_bin = os.environ.get("FIREFOX_BIN")
    if env_bin and Path(env_bin).exists() and Path(env_bin).is_file():
        return Path(env_bin).resolve()

    pkg_root = Path(__file__).resolve().parent.parent
    cwd = Path.cwd().resolve()
    ws = Path(workspace_dir).resolve() if workspace_dir else None

    # Daftar kandidat folder direktori portable
    dirs_to_check: List[Path] = []
    if portable_dir:
        dirs_to_check.append(Path(portable_dir).resolve())
    if ws:
        dirs_to_check.append(ws / "firefox_portable")
    dirs_to_check.extend([
        cwd / "firefox_portable",
        pkg_root / "firefox_portable",
        cwd.parent / "firefox_portable",
        cwd.parent / "firefox-stealth-automation" / "firefox_portable",
        Path("D:/Tools/firefox-stealth-automation/firefox_portable"),
        Path("D:/Tools/image-generator/firefox_portable"),
        Path(r"D:\FirefoxPortable"),
    ])

    subpaths = [
        Path("App") / "Firefox64" / "firefox.exe",
        Path("App") / "Firefox" / "firefox.exe",
        Path("core") / "firefox.exe",
        Path("firefox.exe"),
    ]

    for d in dirs_to_check:
        if d.exists():
            for sp in subpaths:
                candidate = d / sp
                if candidate.exists() and candidate.is_file():
                    return candidate.resolve()

    # Fallback ke sistem Firefox melalui PATH
    sys_ff = shutil.which("firefox") or shutil.which("firefox.exe")
    if sys_ff:
        return Path(sys_ff).resolve()

    # Fallback ke Program Files standar Windows
    prog_files = os.environ.get("PROGRAMFILES", r"C:\Program Files")
    prog_files_x86 = os.environ.get("PROGRAMFILES(X86)", r"C:\Program Files (x86)")
    for pf in (prog_files, prog_files_x86):
        cand = Path(pf) / "Mozilla Firefox" / "firefox.exe"
        if cand.exists() and cand.is_file():
            return cand.resolve()

    return None


class StealthBrowser:
    """Manajer proses peramban Firefox Stealth berbasis Marionette.

    Menangani siklus hidup lengkap subprocess Firefox Portable, pembuatan profil
    terisolasi per proyek kerja, self-healing lockfile, koneksi soket TCP otomatis,
    penutupan anggun (graceful termination), serta context manager.

    Contoh Penggunaan:
        >>> with StealthBrowser(headless=True) as browser:
        ...     browser.driver.navigate("https://bot.sannysoft.com")
        ...     print(browser.driver.title)
    """

    def __init__(
        self,
        firefox_bin: Optional[Union[Path, str]] = None,
        profile_dir: Optional[Union[Path, str]] = None,
        workspace_dir: Optional[Union[Path, str]] = None,
        port: int = 2828,
        headless: bool = True,
        extra_args: Optional[List[str]] = None,
    ) -> None:
        """Inisialisasi manajer proses browser dengan isolasi profil proyek.

        Args:
            firefox_bin: Jalur biner firefox.exe. Jika None, dideteksi otomatis.
            profile_dir: Jalur direktori profil browser. Jika None, diselesaikan
                         ke folder `browser_profile` lokal milik proyek aktif.
            workspace_dir: Direktori root proyek pemanggil.
            port: Port Marionette (default 2828).
            headless: Jalankan tanpa antarmuka grafis (default True).
            extra_args: Argumen baris perintah tambahan untuk Firefox.
        """
        self.workspace_dir = Path(workspace_dir).resolve() if workspace_dir else Path.cwd().resolve()
        self.profile_dir = resolve_profile_dir(profile_dir=profile_dir, workspace_dir=self.workspace_dir)
        self.firefox_bin = Path(firefox_bin).resolve() if firefox_bin else get_firefox_executable(workspace_dir=self.workspace_dir)
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

        Secara otomatis membersihkan lock yatim (parent.lock) dan menyiapkan
        konfigurasi user.js yang dikeraskan sebelum peramban dijalankan.

        Args:
            startup_timeout: Waktu tunggu maksimal peramban siap dalam detik.

        Returns:
            MarionetteDriver: Instansi driver yang sudah terotentikasi dan siap dipakai.

        Raises:
            BrowserProcessError: Jika biner tidak ditemukan atau proses gagal meluncur.
            MarionetteTimeoutError: Jika port Marionette tidak merespons dalam batas waktu.
        """
        if not self.firefox_bin or not self.firefox_bin.exists():
            raise BrowserProcessError(
                f"Biner Firefox tidak ditemukan di: {self.firefox_bin}. "
                "Jalankan 'firefox-stealth setup' atau 'python setup_browser.py' terlebih dahulu."
            )

        # Inisialisasi profil bersih dan bersihkan lockfile yatim
        self.profile_dir.mkdir(parents=True, exist_ok=True)
        clean_profile_locks(self.profile_dir)
        setup_clean_profile(self.profile_dir, port=self.port)

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

        # Tunggu pembukaan port Marionette (Adaptive Fast-Polling 50ms)
        self._driver = MarionetteDriver(host="127.0.0.1", port=self.port)
        start_time = time.time()
        while time.time() - start_time < startup_timeout:
            if self.process.poll() is not None:
                raise BrowserProcessError(
                    f"Proses Firefox berhenti sebelum siap (kode keluar: {self.process.returncode})."
                )
            if self._driver.is_port_open(timeout=0.15):
                break
            time.sleep(0.05)
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

        # Bersihkan lockfile yatim setelah peramban ditutup
        clean_profile_locks(self.profile_dir)
