"""SETUP BROWSER CLI — AUTOMATED FIREFOX PORTABLE BOOTSTRAPPER.

Modul ini bertanggung jawab mengunduh, mengekstrak, dan mengonfigurasi
Mozilla Firefox Portable Edition secara otomatis dari baris perintah (CLI),
memungkinkan proyek untuk dijalankan dari awal (clean install) di mesin mana pun
saat di-clone dari repositori GitHub.
"""

import argparse
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

from rich import box
from rich.console import Console
from rich.panel import Panel
from rich.progress import (
    BarColumn,
    DownloadColumn,
    Progress,
    SpinnerColumn,
    TextColumn,
    TimeRemainingColumn,
    TransferSpeedColumn,
)
from rich.table import Table

# Standar encoding UTF-8 untuk terminal Windows
try:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
except Exception:
    pass

console = Console()

WORKSPACE_DIR = Path(__file__).resolve().parent
DEFAULT_PORTABLE_DIR = WORKSPACE_DIR / "firefox_portable"
DEFAULT_PROFILE_DIR = WORKSPACE_DIR / "browser_profile"

import socket

OFFICIAL_DOWNLOAD_URL = (
    "https://archive.mozilla.org/pub/firefox/releases/115.19.0esr/win64/en-US/Firefox%20Setup%20115.19.0esr.exe"
)
FALLBACK_DOWNLOAD_URL = (
    "https://ftp.mozilla.org/pub/firefox/releases/115.19.0esr/win64/en-US/Firefox%20Setup%20115.19.0esr.exe"
)


class AbortLowSpeedException(Exception):
    """Pengecualian saat kecepatan unduh berada di bawah batas absolut minimum (100 kB/s)."""

    def __init__(self, speed_kbs: float):
        super().__init__(f"Kecepatan {speed_kbs:.1f} kB/s di bawah batas minimum 100 kB/s.")
        self.speed_kbs = speed_kbs


def is_internet_available(timeout: float = 3.0) -> bool:
    """Memeriksa apakah perangkat memiliki koneksi aktif ke jaringan internet."""
    test_hosts = [("1.1.1.1", 53), ("8.8.8.8", 53), ("archive.mozilla.org", 443)]
    for host, port in test_hosts:
        try:
            sock = socket.create_connection((host, port), timeout=timeout)
            sock.close()
            return True
        except (OSError, socket.timeout):
            continue
    return False


def wait_for_internet_recovery() -> None:
    """Menghentikan alur sementara dan meminta pengguna memastikan koneksi stabil sebelum melanjutkan."""
    console.print(
        Panel(
            "[bold red]✗ TIDAK ADA KONEKSI INTERNET TERDETEKSI[/bold red]\n\n"
            "Perangkat Anda saat ini terputus dari jaringan internet atau server tidak dapat dijangkau.\n"
            "[yellow]Pengunduhan dijeda sementara demi keamanan data dan mencegah korupsi berkas.[/yellow]\n\n"
            "[white]Silakan periksa koneksi Wi-Fi/LAN/Data Anda hingga stabil kembali.[/white]\n"
            "[bold green]Jika koneksi internet sudah aktif kembali, tekan [ENTER] untuk melanjutkan unduhan...[/bold green]",
            box=box.ROUNDED,
            title="[red]Peringatan Jaringan Terputus[/red]",
        )
    )
    while True:
        try:
            input()
        except (KeyboardInterrupt, EOFError):
            console.print("\n[dim]Dibatalkan oleh pengguna.[/dim]")
            sys.exit(1)

        console.print("[info]ℹ Menguji kembali ketersediaan jaringan internet...[/info]")
        if is_internet_available():
            console.print("[success]✓ Koneksi internet terdeteksi aktif dan stabil! Melanjutkan unduhan...[/success]")
            break
        else:
            console.print(
                "[warning]⚠ Koneksi internet masih belum terhubung. Silakan periksa jaringan dan tekan [ENTER] kembali.[/warning]"
            )


def _safe_move(src: Path, dst: Path, retries: int = 10, delay: float = 0.3) -> bool:
    """Memindahkan berkas biner secara aman di Windows dengan penanganan lock antivirus/proses lain."""
    import gc
    gc.collect()
    for _ in range(retries):
        try:
            if dst.exists():
                dst.unlink()
            src.rename(dst)
            return True
        except (PermissionError, OSError):
            time.sleep(delay)
    try:
        shutil.copy2(src, dst)
        src.unlink(missing_ok=True)
        return True
    except Exception:
        return False


def get_firefox_executable(portable_dir: Path | None = None) -> Path | None:
    """Mencari jalur berkas firefox.exe portable yang tersedia.

    Args:
        portable_dir (Path | None): Direktori instalasi lokal firefox_portable.

    Returns:
        Path | None: Jalur absolut firefox.exe jika ditemukan, atau None.
    """
    target_dir = portable_dir or DEFAULT_PORTABLE_DIR
    candidates = [
        target_dir / "App" / "Firefox64" / "firefox.exe",
        target_dir / "App" / "Firefox" / "firefox.exe",
        target_dir / "core" / "firefox.exe",
        target_dir / "firefox.exe",
    ]
    for path in candidates:
        if path.exists() and path.is_file():
            return path.resolve()
    return None


def download_file(url: str, dest_path: Path, max_retries: int = 5) -> bool:
    """Mengunduh berkas biner dari URL langsung dengan dukungan auto-resume, retry, dan adaptive speed monitor.

    Args:
        url (str): URL sumber pengunduhan.
        dest_path (Path): Jalur berkas lokal tujuan penyimpanan.
        max_retries (int): Batas maksimal percobaan koneksi ulang jika terjadi gangguan jaringan.

    Returns:
        bool: True jika berhasil diunduh dan ukuran valid.
    """
    try:
        from curl_cffi import requests
    except ImportError:
        import requests  # type: ignore

    dest_path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = dest_path.with_name(dest_path.stem + ".downloading")

    # Jika berkas unduhan lengkap sudah ada di temp_path (misal dari percobaan sebelumnya)
    if temp_path.exists() and temp_path.stat().st_size >= 50 * 1024 * 1024:
        if _safe_move(temp_path, dest_path):
            console.print(
                f"[success]✓ Berkas installer sudah lengkap terunduh:[/success] {dest_path.name} "
                f"({dest_path.stat().st_size // (1024*1024)} MB)"
            )
            return True

    # Pengecekan koneksi internet sebelum memulai
    if not is_internet_available():
        wait_for_internet_recovery()

    console.print(f"[info]ℹ[/info] Menghubungi server CDN: [cyan]{url}[/cyan]")

    urls_to_try = [url]
    if url != FALLBACK_DOWNLOAD_URL:
        urls_to_try.append(FALLBACK_DOWNLOAD_URL)

    current_tier_kb = 500.0
    slow_streak = 0

    for current_url in urls_to_try:
        attempt = 0
        while attempt < max_retries:
            attempt += 1
            session = None
            resp = None
            try:
                # Verifikasi internet sebelum menembak request
                if not is_internet_available():
                    wait_for_internet_recovery()
                    attempt = 1  # Reset attempt setelah internet pulih

                existing_bytes = 0
                if temp_path.exists():
                    existing_bytes = temp_path.stat().st_size

                # Jika berkas sudah berukuran penuh (minimal 50 MB), langsung pindahkan
                if existing_bytes >= 50 * 1024 * 1024:
                    if _safe_move(temp_path, dest_path):
                        console.print(
                            f"[success]✓ Pengunduhan selesai:[/success] {dest_path.name} "
                            f"({dest_path.stat().st_size // (1024*1024)} MB)"
                        )
                        return True

                headers = {}
                if existing_bytes > 0:
                    headers["Range"] = f"bytes={existing_bytes}-"
                    console.print(
                        f"[info]ℹ Melanjutkan unduhan dari byte {existing_bytes} "
                        f"({existing_bytes // (1024*1024)} MB) [Percobaan {attempt}/{max_retries}]...[/info]"
                    )

                session = requests.Session()
                resp = session.get(
                    current_url,
                    stream=True,
                    impersonate="chrome124",
                    allow_redirects=True,
                    headers=headers,
                    timeout=30,
                )

                # Tangani HTTP 416 (Range Not Satisfiable) jika file sudah komplit
                if resp.status_code == 416:
                    if temp_path.exists() and temp_path.stat().st_size >= 50 * 1024 * 1024:
                        if _safe_move(temp_path, dest_path):
                            console.print(
                                f"[success]✓ Pengunduhan selesai:[/success] {dest_path.name} "
                                f"({dest_path.stat().st_size // (1024*1024)} MB)"
                            )
                            return True
                    if temp_path.exists():
                        temp_path.unlink(missing_ok=True)
                    continue

                is_resume = (resp.status_code == 206)
                if not is_resume:
                    existing_bytes = 0
                    file_mode = "wb"
                    total_size = int(resp.headers.get("content-length", 0))
                else:
                    file_mode = "ab"
                    content_len = int(resp.headers.get("content-length", 0))
                    total_size = existing_bytes + content_len

                resp.raise_for_status()

                # Pemantauan Kecepatan Adaptif (500 -> 300 -> 100 kB/s)
                start_stream_time = time.time()
                last_eval_time = start_stream_time
                bytes_in_window = 0
                warmup_seconds = 3.0
                eval_interval = 3.0

                with Progress(
                    SpinnerColumn(),
                    TextColumn("[bold blue]{task.description}"),
                    BarColumn(bar_width=40),
                    DownloadColumn(),
                    TransferSpeedColumn(),
                    TimeRemainingColumn(),
                    console=console,
                ) as progress:
                    task = progress.add_task(
                        "Mengunduh Firefox Portable...",
                        total=total_size if total_size > 0 else None,
                        completed=existing_bytes,
                    )
                    with open(temp_path, file_mode) as f:
                        for chunk in resp.iter_content(chunk_size=65536):
                            if not chunk:
                                continue
                            f.write(chunk)
                            chunk_len = len(chunk)
                            progress.update(task, advance=chunk_len)
                            bytes_in_window += chunk_len

                            now = time.time()
                            # Evaluasi kecepatan setelah fase pemanasan awal
                            if now - start_stream_time > warmup_seconds and (now - last_eval_time) >= eval_interval:
                                window_duration = now - last_eval_time
                                current_speed_kbs = (bytes_in_window / 1024.0) / window_duration
                                last_eval_time = now
                                bytes_in_window = 0

                                if current_speed_kbs < current_tier_kb:
                                    slow_streak += 1
                                    if current_tier_kb == 500.0 and slow_streak >= 3:
                                        current_tier_kb = 300.0
                                        slow_streak = 0
                                        console.print(
                                            f"\n[yellow]⚠ Kecepatan unduh ({current_speed_kbs:.1f} kB/s) di bawah standar 500 kB/s (3x).\n"
                                            f"  Menyesuaikan toleransi ke batas 300 kB/s...[/yellow]"
                                        )
                                    elif current_tier_kb == 300.0 and slow_streak >= 3:
                                        current_tier_kb = 100.0
                                        slow_streak = 0
                                        console.print(
                                            f"\n[yellow]⚠ Kecepatan unduh ({current_speed_kbs:.1f} kB/s) di bawah standar 300 kB/s (3x).\n"
                                            f"  Menyesuaikan toleransi ke batas minimum 100 kB/s...[/yellow]"
                                        )
                                    elif current_tier_kb == 100.0 and slow_streak >= 3:
                                        raise AbortLowSpeedException(current_speed_kbs)
                                else:
                                    slow_streak = 0

                # Tutup session dan response agar tidak ada file handle yang tertahan di Windows
                try:
                    resp.close()
                except Exception:
                    pass
                try:
                    session.close()
                except Exception:
                    pass

                # Verifikasi ukuran akhir dan pindahkan dengan penanganan lock Windows
                if temp_path.exists() and temp_path.stat().st_size >= 50 * 1024 * 1024:
                    if _safe_move(temp_path, dest_path):
                        console.print(
                            f"[success]✓ Pengunduhan selesai:[/success] {dest_path.name} "
                            f"({dest_path.stat().st_size // (1024*1024)} MB)"
                        )
                        return True

            except AbortLowSpeedException as err:
                console.print(
                    Panel(
                        f"[bold red]⚠ KECEPATAN UNDUH TERLALU LAMBAT ({err.speed_kbs:.1f} kB/s < 100 kB/s)[/bold red]\n\n"
                        "Pengunduhan telah diuji dan kecepatan transfer terdeteksi di bawah batas minimum 100 kB/s.\n"
                        "[yellow]Pengunduhan dihentikan sementara untuk memastikan koneksi internet Anda stabil.[/yellow]\n\n"
                        "[white]Silakan periksa koneksi internet Anda (sinyal provider, penggunaan bandwidth, atau hotspot).[/white]\n"
                        "[bold green]Jika koneksi internet sudah membaik, tekan [ENTER] untuk melanjutkan unduhan...[/bold green]",
                        box=box.ROUNDED,
                        title="[red]Peringatan Batas Kecepatan Minimum[/red]",
                    )
                )
                try:
                    input()
                except (KeyboardInterrupt, EOFError):
                    console.print("\n[dim]Dibatalkan oleh pengguna.[/dim]")
                    sys.exit(1)

                current_tier_kb = 500.0
                slow_streak = 0
                attempt = 0
                continue

            except Exception as err:
                # Periksa apakah error disebabkan oleh koneksi internet yang putus total
                if not is_internet_available():
                    wait_for_internet_recovery()
                    attempt = 0
                    continue

                console.print(f"[warning]⚠ Gangguan koneksi ({err}). Menyambung ulang dalam 2 detik...[/warning]")
                time.sleep(2)

            finally:
                if resp is not None:
                    try:
                        resp.close()
                    except Exception:
                        pass
                if session is not None:
                    try:
                        session.close()
                    except Exception:
                        pass

    console.print("[error]✗ Batas percobaan pengunduhan habis. Periksa koneksi internet Anda.[/error]")
    return False


def install_portable_package(installer_path: Path, target_dir: Path) -> bool:
    """Mengekstrak paket instalasi PortableApps (.paf.exe) secara senyap tanpa dialog GUI.

    Args:
        installer_path (Path): Lokasi berkas installer .paf.exe.
        target_dir (Path): Direktori tujuan instalasi.

    Returns:
        bool: True jika biner firefox.exe berhasil terpasang di target.
    """
    console.print(f"[info]ℹ[/info] Mengekstrak paket instalasi ke: [cyan]{target_dir}[/cyan]...")
    target_dir.mkdir(parents=True, exist_ok=True)

    # 1. Prioritaskan ekstraksi langsung menggunakan 7-Zip (100% senyap, andal, tanpa GUI)
    seven_zip_candidates = [
        Path(r"C:\Program Files\7-Zip\7z.exe"),
        Path(r"C:\Program Files (x86)\7-Zip\7z.exe"),
        Path(shutil.which("7z") or ""),
    ]
    seven_zip = next((p for p in seven_zip_candidates if p and p.exists()), None)
    if seven_zip:
        console.print(f"[info]ℹ Menggunakan 7-Zip untuk ekstraksi: [cyan]{seven_zip}[/cyan][/info]")
        cmd_7z = [str(seven_zip), "x", str(installer_path.resolve()), f"-o{target_dir.resolve()}", "-y"]
        try:
            res = subprocess.run(cmd_7z, capture_output=True, text=True, timeout=300)
            if res.returncode == 0:
                # Jika diekstrak dari installer resmi Mozilla (berisi folder core/), tata ke App/Firefox64
                core_dir = target_dir / "core"
                app_ff64 = target_dir / "App" / "Firefox64"
                if core_dir.exists() and (core_dir / "firefox.exe").exists():
                    app_ff64.mkdir(parents=True, exist_ok=True)
                    for item in core_dir.iterdir():
                        dest_item = app_ff64 / item.name
                        if dest_item.exists():
                            if dest_item.is_dir():
                                shutil.rmtree(dest_item, ignore_errors=True)
                            else:
                                dest_item.unlink(missing_ok=True)
                        shutil.move(str(item), str(app_ff64))
                    shutil.rmtree(core_dir, ignore_errors=True)

                ff_bin = get_firefox_executable(target_dir)
                if ff_bin and ff_bin.exists():
                    console.print(f"[success]✓ Firefox Portable berhasil diekstrak via 7-Zip:[/success] [cyan]{ff_bin}[/cyan]")
                    return True
        except Exception as err:
            console.print(f"[warning]⚠ Ekstraksi 7-Zip gagal, mencoba fallback installer:[/warning] {err}")

    # 2. Fallback: Eksekusi installer NSIS bawaan
    cmd = [str(installer_path.resolve()), "/S", f"/D={target_dir.resolve()}"]

    try:
        proc = subprocess.run(cmd, timeout=300, capture_output=True)
    except Exception as err:
        console.print(f"[error]✗ Kegagalan saat mengeksekusi installer:[/error] {err}")
        return False

    # Tunggu ekstraksi berkas biner firefox.exe (hingga 30 detik)
    for _ in range(15):
        time.sleep(2.0)
        ff_bin = get_firefox_executable(target_dir)
        if ff_bin and ff_bin.exists():
            console.print(f"[success]✓ Firefox Portable berhasil dipasang:[/success] [cyan]{ff_bin}[/cyan]")
            return True

    console.print(f"[error]✗ Berkas biner firefox.exe tidak ditemukan di {target_dir} pasca-instalasi.[/error]")
    return False


def setup_clean_profile(profile_dir: Path | None = None) -> Path:
    """Menginisialisasi direktori profil peramban terisolasi dengan setelan dasar.

    Args:
        profile_dir (Path | None): Direktori profil peramban.

    Returns:
        Path: Direktori profil yang siap digunakan.
    """
    p_dir = profile_dir or DEFAULT_PROFILE_DIR
    p_dir.mkdir(parents=True, exist_ok=True)

    user_js = p_dir / "user.js"
    base_prefs = """// KONFIGURASI OTOMASI MARIONETTE BASELINE
user_pref("marionette.enabled", true);
user_pref("marionette.port", 2828);
user_pref("dom.webdriver.enabled", false);
user_pref("toolkit.telemetry.enabled", false);
user_pref("toolkit.telemetry.reportingpolicy.firstRun", false);
user_pref("browser.sessionstore.resume_from_crash", false);

// HARDENING WEBRTC & PRIVASI JARINGAN (ITERASI 2)
user_pref("media.peerconnection.enabled", true);
user_pref("media.peerconnection.ice.no_host", true);
user_pref("media.peerconnection.ice.default_address_only", true);
"""
    if not user_js.exists():
        user_js.write_text(base_prefs, encoding="utf-8")
        console.print(f"[success]✓ Berkas profil dasar dibuat:[/success] {user_js}")
    return p_dir


def main() -> int:
    """Fungsi titik masuk CLI bootstrapper browser."""
    parser = argparse.ArgumentParser(
        description="Firefox Portable Automatic Bootstrapper & Environment Provisioner."
    )
    parser.add_argument("--download", action="store_true", help="Paksa download ulang Firefox Portable resmi")
    parser.add_argument("--force", action="store_true", help="Timpa instalasi lama jika sudah ada")
    parser.add_argument("--status", action="store_true", help="Periksa status ketersediaan Firefox Portable saat ini")

    args = parser.parse_args()

    console.print(
        Panel.fit(
            "[bold cyan]FIREFOX PORTABLE BOOTSTRAPPER — STEALTH AUTOMATION[/bold cyan]\n"
            "[muted]Otomasi Penyediaan Lingkungan Peramban Mandiri Tanpa Ketergantungan Eksternal[/muted]",
            box=box.ROUNDED,
        )
    )

    current_bin = get_firefox_executable()

    if args.status:
        table = Table(box=box.ROUNDED)
        table.add_column("Komponen", style="cyan")
        table.add_column("Status / Lokasi", style="bold green" if current_bin else "bold red")
        table.add_row("Firefox Portable Biner", str(current_bin) if current_bin else "Belum Terpasang")
        table.add_row("Direktori Profil", str(DEFAULT_PROFILE_DIR))
        console.print(table)
        return 0 if current_bin else 1

    if current_bin and not args.download and not args.force:
        console.print(f"[success]✓ Firefox Portable sudah siap digunakan di:[/success] [cyan]{current_bin}[/cyan]")
        setup_clean_profile()
        return 0

    # Unduh dan pasang
    installer_file = WORKSPACE_DIR / "temp_firefox_installer.paf.exe"
    ok = download_file(OFFICIAL_DOWNLOAD_URL, installer_file)
    if not ok:
        console.print("[error]✗ Gagal mengunduh installer. Periksa koneksi internet Anda.[/error]")
        return 1

    installed = install_portable_package(installer_file, DEFAULT_PORTABLE_DIR)

    # Bersihkan file installer sementara
    if installer_file.exists():
        try:
            installer_file.unlink()
        except Exception:
            pass

    if installed:
        setup_clean_profile()
        console.print(
            Panel(
                "[bold green]INSTALASI FIREFOX PORTABLE SELESAI & LENGKAP![/bold green]\n"
                f"Lokasi Biner : [cyan]{get_firefox_executable(DEFAULT_PORTABLE_DIR)}[/cyan]\n"
                f"Folder Profil: [cyan]{DEFAULT_PROFILE_DIR}[/cyan]\n"
                "[muted]Siap digunakan untuk otomasi tanpa perlu konfigurasi manual.[/muted]",
                box=box.ROUNDED,
            )
        )
        return 0
    else:
        return 1


if __name__ == "__main__":
    sys.exit(main())
