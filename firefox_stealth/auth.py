"""AUTHENTICATION ENGINE & SESSION VAULT — FIREFOX STEALTH AUTOMATION.

Menyediakan kapabilitas login otomatis (Google Flow, Google Accounts, atau portal web kustom)
serta transfer sesi cookie secara atomik ke cookies.sqlite profil Firefox Portable lokal.
Mendukung isolasi profil per proyek agar setiap folder proyek memiliki sesi akun terpisah.
"""

import argparse
import json
import os
import random
import re
import shutil
import sqlite3
import subprocess
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Union
from urllib.parse import urlparse

from rich import box
from rich.console import Console
from rich.panel import Panel
from rich.prompt import Prompt
from rich.theme import Theme

from firefox_stealth.browser import get_firefox_executable
from firefox_stealth.driver import MarionetteDriver
from firefox_stealth.profile import (
    clean_profile_locks,
    resolve_profile_dir,
    save_playwright_cookies_to_firefox,
    setup_clean_profile,
)

CUSTOM_THEME = Theme(
    {
        "info": "cyan",
        "success": "bold green",
        "warning": "bold yellow",
        "error": "bold red",
        "accent": "bold magenta",
        "muted": "dim white",
        "gold": "bold yellow",
        "brand": "bold color(208)",
    }
)
console = Console(theme=CUSTOM_THEME)

FLOW_HOME_URL = "https://flow.google.com/"


def download_chrome_portable(target_dir: Path) -> Optional[Path]:
    """Mengunduh dan mengekstrak biner Chrome Portable resmi dari Google CDN via 7-Zip atau ZipFile."""
    import urllib.request
    from rich.progress import (
        BarColumn,
        DownloadColumn,
        Progress,
        SpinnerColumn,
        TextColumn,
        TimeRemainingColumn,
        TransferSpeedColumn,
    )

    console.print(
        Panel(
            "[bold cyan]PENYEDIAAN BINER MESIN OTOMASI MANDIRI (CHROME PORTABLE)[/bold cyan]\n\n"
            "Google Chrome tidak ditemukan di sistem Windows. Sistem akan mengunduh biner\n"
            "[white]Chrome for Testing Win64 (Resmi Google)[/white] langsung ke folder proyek lokal.\n"
            "Biner ini 100% portabel dan terisolasi di dalam proyek.",
            box=box.ROUNDED,
            title="[yellow]Auto Provisioning Engine[/yellow]",
        )
    )

    download_url = "https://storage.googleapis.com/chrome-for-testing-public/156.0.8078.47/win64/chrome-win64.zip"
    try:
        api_url = "https://googlechromelabs.github.io/chrome-for-testing/last-known-good-versions-with-downloads.json"
        req = urllib.request.Request(api_url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=5) as r:
            data = json.loads(r.read().decode())
            stable = data["channels"]["Stable"]
            download_url = next(d["url"] for d in stable["downloads"]["chrome"] if d["platform"] == "win64")
    except Exception:
        pass

    temp_zip = target_dir.parent / "temp_chrome.zip"
    target_dir.mkdir(parents=True, exist_ok=True)

    console.print(f"[info]Mengunduh Chrome Portable dari Google CDN...[/info]")
    try:
        req = urllib.request.Request(download_url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=60) as resp, open(temp_zip, "wb") as f_out:
            total_size = int(resp.headers.get("content-length", 0))
            with Progress(
                SpinnerColumn(),
                TextColumn("[progress.description]{task.description}"),
                BarColumn(),
                DownloadColumn(),
                TransferSpeedColumn(),
                TimeRemainingColumn(),
                console=console,
            ) as progress:
                task = progress.add_task("[cyan]Mengunduh Chrome Win64...", total=total_size)
                while True:
                    chunk = resp.read(65536)
                    if not chunk:
                        break
                    f_out.write(chunk)
                    progress.update(task, advance=len(chunk))

        console.print("[info]Mengekstrak paket biner via 7-Zip atau modul internal...[/info]")
        seven_zip_candidates = [
            Path(r"C:\Program Files\7-Zip\7z.exe"),
            Path(r"C:\Program Files (x86)\7-Zip\7z.exe"),
            Path(shutil.which("7z") or ""),
        ]
        seven_zip = next((p for p in seven_zip_candidates if p and p.exists()), None)
        if seven_zip:
            cmd = [str(seven_zip), "x", str(temp_zip.resolve()), f"-o{target_dir.resolve()}", "-y"]
            subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=300)
            extracted_sub = target_dir / "chrome-win64"
            if extracted_sub.exists():
                for item in extracted_sub.iterdir():
                    dest_item = target_dir / item.name
                    if dest_item.exists():
                        if dest_item.is_dir():
                            shutil.rmtree(dest_item, ignore_errors=True)
                        else:
                            dest_item.unlink(missing_ok=True)
                    shutil.move(str(item), str(target_dir))
                shutil.rmtree(extracted_sub, ignore_errors=True)
        else:
            import zipfile
            with zipfile.ZipFile(temp_zip, "r") as zf:
                zf.extractall(target_dir)
            extracted_sub = target_dir / "chrome-win64"
            if extracted_sub.exists():
                for item in extracted_sub.iterdir():
                    dest_item = target_dir / item.name
                    if dest_item.exists():
                        if dest_item.is_dir():
                            shutil.rmtree(dest_item, ignore_errors=True)
                        else:
                            dest_item.unlink(missing_ok=True)
                    shutil.move(str(item), str(target_dir))
                shutil.rmtree(extracted_sub, ignore_errors=True)

        if temp_zip.exists():
            temp_zip.unlink(missing_ok=True)

        chrome_bin = target_dir / "chrome.exe"
        if chrome_bin.exists():
            console.print(f"[success]✓ Chrome Portable berhasil disiapkan di:[/success] [cyan]{chrome_bin}[/cyan]")
            return chrome_bin

    except Exception as err:
        console.print(f"[error]✗ Gagal mengunduh Chrome Portable:[/error] {err}")
        if temp_zip.exists():
            temp_zip.unlink(missing_ok=True)
        return None

    return None


def ensure_local_chrome_engine(target_dir: Optional[Path] = None) -> Optional[Path]:
    """Memastikan biner peramban otomasi lokal (chrome_portable atau sistem) tersedia."""
    pkg_root = Path(__file__).resolve().parent.parent
    cwd = Path.cwd().resolve()
    base_dir = target_dir or (cwd / "chrome_portable")

    local_bin = base_dir / "chrome.exe"
    if local_bin.exists():
        return local_bin

    # Cek kandidat di Tools atau repo root
    pkg_chrome = pkg_root / "chrome_portable" / "chrome.exe"
    if pkg_chrome.exists():
        return pkg_chrome

    tools_chrome = Path("D:/Tools/firefox-stealth-automation/chrome_portable/chrome.exe")
    if tools_chrome.exists():
        return tools_chrome

    # 1. Jalur Cepat: Periksa apakah tersedia di Program Files sistem
    sys_chrome = Path(r"C:\Program Files\Google\Chrome\Application")
    if sys_chrome.exists() and (sys_chrome / "chrome.exe").exists():
        return (sys_chrome / "chrome.exe")

    sys_chrome_x86 = Path(r"C:\Program Files (x86)\Google\Chrome\Application")
    if sys_chrome_x86.exists() and (sys_chrome_x86 / "chrome.exe").exists():
        return (sys_chrome_x86 / "chrome.exe")

    which_chrome = shutil.which("chrome") or shutil.which("google-chrome")
    if which_chrome:
        return Path(which_chrome).resolve()

    # 2. Unduh mandiri jika tidak ada sama sekali di sistem
    return download_chrome_portable(base_dir)


def verify_session_headless(
    target_url: str = FLOW_HOME_URL,
    profile_dir: Optional[Union[Path, str]] = None,
    firefox_bin: Optional[Union[Path, str]] = None,
    timeout: float = 25.0,
) -> Dict[str, Any]:
    """Meluncurkan Firefox Portable headless untuk memverifikasi kanvas Google Flow atau halaman web secara senyap.

    Args:
        target_url: URL target verifikasi sesi.
        profile_dir: Direktori profil peramban sasaran. Jika None, menggunakan profil proyek aktif.
        firefox_bin: Jalur biner firefox.exe. Jika None, dideteksi otomatis.
        timeout: Batas waktu tunggu verifikasi dalam detik.

    Returns:
        Dict[str, Any]: Status verifikasi ('success', 'url', 'title', 'message').
    """
    target_profile = resolve_profile_dir(profile_dir)
    bin_path = Path(firefox_bin).resolve() if firefox_bin else get_firefox_executable()

    if not bin_path or not bin_path.exists():
        return {"success": False, "message": f"Biner Firefox tidak ditemukan di sistem."}

    cookies_db = target_profile / "cookies.sqlite"
    has_target_cookie = False
    if cookies_db.exists():
        try:
            conn = sqlite3.connect(f"file:{cookies_db}?mode=ro", uri=True)
            cur = conn.cursor()
            cur.execute("SELECT count(*) FROM moz_cookies WHERE host LIKE '%google.com%' OR host LIKE '%flow%'")
            row = cur.fetchone()
            count = row[0] if row else 0
            conn.close()
            if count > 0:
                has_target_cookie = True
        except Exception:
            pass

    if not has_target_cookie:
        return {
            "success": False,
            "status": "fresh_install",
            "url": f"{target_url.rstrip('/')}/about",
            "message": "Profil peramban baru terpasang (kondisi bersih). Akun belum terhubung.",
        }

    clean_profile_locks(target_profile)
    setup_clean_profile(target_profile, port=2828)

    cmd = [
        str(bin_path),
        "-no-remote",
        "-headless",
        "-marionette",
        "-profile",
        str(target_profile),
    ]

    env = os.environ.copy()
    env["MOZ_CRASHREPORTER_DISABLE"] = "1"
    env["MOZ_CRASHREPORTER_NO_REPORT"] = "1"

    proc = subprocess.Popen(cmd, env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    driver = MarionetteDriver(host="127.0.0.1", port=2828)

    try:
        opened = False
        start_wait = time.time()
        while time.time() - start_wait < 10.0:
            if driver.is_port_open(timeout=0.5):
                opened = True
                break
            time.sleep(0.3)

        if not opened:
            return {"success": False, "message": "Gagal terhubung ke port otomasi Marionette (2828)."}

        driver.connect(timeout=15.0)
        driver.navigate(target_url)

        start_poll = time.time()
        last_url = ""
        while time.time() - start_poll < timeout:
            time.sleep(1.5)
            check_script = """
            const url = window.location.href.toLowerCase();
            const hasDashboard = !!document.querySelector('aisandbox-root, flow-project-shell, flow-prompt-box, .project-card, [data-test-id="project-card"]');
            const isAuth = url.includes('accounts.google.com') || url.includes('/about');
            return {
                url: window.location.href,
                title: document.title,
                hasDashboard: hasDashboard,
                isAuth: isAuth,
                loggedIn: hasDashboard && !url.includes('/about')
            };
            """
            try:
                state = driver.execute_script(check_script)
                if isinstance(state, dict):
                    last_url = state.get("url", "")
                    if state.get("loggedIn"):
                        return {
                            "success": True,
                            "url": last_url,
                            "title": state.get("title", ""),
                            "message": "Berhasil terotentikasi dan sesi aktif!",
                        }
                    if "/about" in last_url.lower():
                        return {
                            "success": False,
                            "status": "not_logged_in",
                            "url": last_url,
                            "title": state.get("title", ""),
                            "message": "Akun belum masuk (halaman informasi publik /about).",
                        }
                    if state.get("isAuth") and "accounts.google.com" in last_url:
                        return {
                            "success": False,
                            "status": "not_logged_in",
                            "url": last_url,
                            "title": state.get("title", ""),
                            "message": "Sesi belum aktif (berada di halaman login accounts.google.com).",
                        }
            except Exception:
                pass

        return {
            "success": False,
            "status": "timeout",
            "url": last_url,
            "message": "Waktu tunggu habis saat memuat halaman target.",
        }

    finally:
        driver.close()
        try:
            proc.terminate()
            proc.wait(timeout=4.0)
        except Exception:
            try:
                proc.kill()
            except Exception:
                pass
        clean_profile_locks(target_profile)


def automated_google_login(
    email: Optional[str] = None,
    password: Optional[str] = None,
    profile_dir: Optional[Union[Path, str]] = None,
    target_url: str = FLOW_HOME_URL,
) -> bool:
    """Melakukan otomatisasi penuh login Google secara 100% Full CLI dengan isolasi profil proyek.

    Args:
        email: Alamat email akun Google (jika None, akan ditanyakan interaktif via Prompt).
        password: Kata sandi akun Google (jika None, akan ditanyakan interaktif via Prompt).
        profile_dir: Direktori profil Firefox sasaran untuk menyimpan token cookies.
        target_url: URL tujuan setelah berhasil login (default: Google Flow).

    Returns:
        bool: True jika login berhasil dan cookie tersimpan, False jika gagal.
    """
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        console.print("[error]✗ Pustaka playwright belum terpasang. Jalankan: uv pip install playwright[/error]")
        return False

    target_profile = resolve_profile_dir(profile_dir)
    target_profile.mkdir(parents=True, exist_ok=True)

    chrome_bin = ensure_local_chrome_engine()
    if not chrome_bin or not chrome_bin.exists():
        console.print("[error]✗ Biner mesin peramban otomasi tidak ditemukan.[/error]")
        return False

    console.print(
        Panel(
            f"[bold green]OTOMASI LOGIN GOOGLE (100% FULL CLI)[/bold green]\n\n"
            f"• Target URL   : [cyan]{target_url}[/cyan]\n"
            f"• Profil Sasaran: [yellow]{target_profile}[/yellow] (Isolasi Proyek)\n"
            f"• Sesi berjalan 100% senyap di latar belakang (mode headless murni).\n"
            f"• Mendukung konfirmasi verifikasi 2-Langkah (2FA) di ponsel Anda.\n"
            f"• Token sesi disimpan langsung ke cookies.sqlite lokal proyek.",
            box=box.ROUNDED,
            title="[cyan]Isolated Browser Profile Authenticator[/cyan]",
        )
    )

    if not email:
        email = Prompt.ask("[cyan]Masukkan Email Google Anda[/cyan]")
    if not password:
        password = Prompt.ask("[cyan]Masukkan Kata Sandi Google[/cyan]", password=True)

    if not email or not password:
        console.print("[error]✗ Email dan sandi wajib diisi.[/error]")
        return False

    console.print("\n[info]Memulai mesin peramban otomasi lokal mandiri (Full CLI)...[/info]")

    with sync_playwright() as p:
        try:
            launch_kwargs = {
                "headless": True,
                "executable_path": str(chrome_bin),
                "args": [
                    "--disable-blink-features=AutomationControlled",
                    "--no-first-run",
                    "--no-default-browser-check",
                ],
            }

            browser = p.chromium.launch(**launch_kwargs)
            context = browser.new_context(
                viewport={"width": 1280, "height": 800},
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/136.0.0.0 Safari/537.36",
            )
            page = context.new_page()

            console.print("[info]Membuka portal Google Sign-In...[/info]")
            login_entry_url = f"https://accounts.google.com/signin/v2/identifier?continue={target_url}"
            page.goto(login_entry_url, wait_until="domcontentloaded")

            # Cek jika layar menampilkan pilihan akun yang sudah ada sebelumnya
            if not page.query_selector("#identifierId"):
                use_another = page.query_selector(
                    "div:has-text('Use another account'), div:has-text('Gunakan akun lain')"
                )
                if use_another and use_another.is_visible():
                    use_another.click()
                    time.sleep(2)

            page.wait_for_selector("#identifierId", timeout=20000)

            # 1. Ketik email dengan jeda manusiawi
            console.print(f"[info]Mengisi email:[/info] [cyan]{email}[/cyan]")
            for ch in email:
                page.type("#identifierId", ch, delay=random.randint(30, 80))
            time.sleep(0.5)

            console.print("[info]Mengirim formulir email...[/info]")
            page.press("#identifierId", "Enter")
            time.sleep(1)
            next_btn = page.query_selector("#identifierNext button, #identifierNext, button[jsname='LgbsSe']")
            if next_btn and next_btn.is_visible():
                try:
                    next_btn.click()
                except Exception:
                    pass
            time.sleep(4)

            # Evaluasi respons email
            if "signin/rejected" in page.url:
                console.print(
                    "[error]✗ Google menolak akses (signin/rejected). Lingkungan belum memenuhi kriteria attestation.[/error]"
                )
                browser.close()
                return False

            body_text = page.inner_text("body")
            if (
                "Couldn’t find your Google Account" in body_text
                or "Tidak dapat menemukan Akun Google" in body_text
            ):
                console.print(f"[error]✗ Akun Google '{email}' tidak ditemukan.[/error]")
                browser.close()
                return False

            if "Account deleted" in body_text or "Akun dihapus" in body_text:
                console.print(f"[error]✗ Akun Google '{email}' telah dinonaktifkan/dihapus.[/error]")
                browser.close()
                return False

            # 2. Tunggu field kata sandi
            console.print("[info]Menunggu formulir kata sandi...[/info]")
            pwd_sel = 'input[type="password"]:not([name="hiddenPassword"]), input[name="Passwd"]'
            page.wait_for_selector(pwd_sel, timeout=20000)

            console.print("[info]Mengisi kata sandi secara aman...[/info]")
            for ch in password:
                page.type(pwd_sel, ch, delay=random.randint(30, 80))
            time.sleep(0.5)

            console.print("[info]Mengirim kata sandi...[/info]")
            page.press(pwd_sel, "Enter")
            time.sleep(1)
            pwd_next = page.query_selector("#passwordNext button, #passwordNext, button[jsname='LgbsSe']")
            if pwd_next and pwd_next.is_visible():
                try:
                    pwd_next.click()
                except Exception:
                    pass
            time.sleep(5)

            # Evaluasi respons kata sandi
            body_post_pwd = page.inner_text("body")
            if "Wrong password" in body_post_pwd or "Sandi salah" in body_post_pwd:
                console.print("[error]✗ Kata sandi yang Anda masukkan salah.[/error]")
                browser.close()
                return False

            # 3. Penanganan Verifikasi 2FA / Device Challenge
            notified_2fa = False
            start_wait_auth = time.time()
            max_timeout = 120.0

            with console.status(
                "[bold cyan]Menunggu konfirmasi autentikasi di background...[/bold cyan]",
                spinner="dots",
            ):
                while time.time() - start_wait_auth < max_timeout:
                    try:
                        curr_url = page.url
                        parsed = urlparse(curr_url)

                        if "signin/rejected" in curr_url:
                            console.print("\n[error]✗ Google menolak akses (signin/rejected).[/error]")
                            browser.close()
                            return False

                        if "myaccount.google.com" in curr_url:
                            try:
                                page.goto(target_url, wait_until="commit")
                            except Exception:
                                pass
                            time.sleep(2)
                            continue

                        # Cek apakah sudah mencapai host target
                        target_netloc = urlparse(target_url).netloc
                        is_target_domain = (
                            parsed.netloc == target_netloc
                            or parsed.netloc.endswith(f".{target_netloc}")
                        ) and not parsed.path.startswith("/about")

                        if is_target_domain:
                            console.print(f"\n[success]✓ BERHASIL TERAUTENTIKASI DI {target_netloc.upper()}![/success]")
                            time.sleep(3)
                            cookies = context.cookies()
                            saved_count = save_playwright_cookies_to_firefox(
                                cookies,
                                profile_dir=target_profile,
                                clear_domains=["google", "flow", "youtube"],
                            )
                            console.print(
                                f"[success]✓ {saved_count} token cookie berhasil disimpan ke [cyan]{target_profile / 'cookies.sqlite'}[/cyan]![/success]"
                            )
                            browser.close()

                            console.print("[info]Memverifikasi sesi pada Firefox Portable lokal...[/info]")
                            ver = verify_session_headless(target_url=target_url, profile_dir=target_profile)
                            _print_verify_result(ver)
                            return True

                        # Lewati dialog opsional Google seperti 'Not now'
                        skip_btn = page.query_selector(
                            "button:has-text('Not now'), button:has-text('Jangan sekarang'), button:has-text('Skip'), button:has-text('Lewati')"
                        )
                        if skip_btn and skip_btn.is_visible():
                            try:
                                skip_btn.click()
                                time.sleep(2)
                            except Exception:
                                pass

                        # Cek 2FA PIN
                        pin_input = page.query_selector(
                            "input#idvPin, input[name='Pin'], input[type='tel'], input#totpPin"
                        )
                        if pin_input and pin_input.is_visible():
                            console.print("\n[gold]📱 Google meminta 6-digit kode verifikasi (SMS / Authenticator):[/gold]")
                            code = Prompt.ask("[cyan]Masukkan Kode Verifikasi[/cyan]")
                            pin_input.fill(code.strip())
                            pin_next = page.query_selector(
                                "#idvPreregisteredPhoneNext, #totpNext, button[jsname='LgbsSe']"
                            )
                            if pin_next:
                                pin_next.click()
                            else:
                                page.keyboard.press("Enter")
                            time.sleep(4)
                            continue

                        # Cek recovery email
                        rec_input = page.query_selector(
                            "input#knowledge-preregistered-email-response, input[name='knowledgePreregisteredEmailResponse']"
                        )
                        if rec_input and rec_input.is_visible():
                            console.print("\n[gold]📧 Google meminta konfirmasi email pemulihan:[/gold]")
                            rec_val = Prompt.ask("[cyan]Masukkan Email Pemulihan[/cyan]")
                            rec_input.fill(rec_val.strip())
                            rec_input.press("Enter")
                            time.sleep(3)
                            continue

                        # Cek notifikasi ponsel
                        page_text = page.inner_text("body")
                        is_2fa_screen = any(
                            kw in page_text.lower()
                            for kw in [
                                "check your",
                                "periksa ponsel",
                                "periksa tablet",
                                "ketuk ya",
                                "tap yes",
                                "2-step",
                                "2 langkah",
                                "verifikasi 2 langkah",
                                "verifikasi perangkat",
                                "google sent a notification",
                                "google mengirim notifikasi",
                                "mengirimkan notifikasi",
                                "pilih angka",
                                "select the number",
                                "verify it's you",
                                "verifikasi bahwa ini memang anda",
                            ]
                        )

                        if is_2fa_screen and not notified_2fa:
                            notified_2fa = True
                            match_num = None
                            for sel in [
                                ".f9UGee",
                                "div[data-number]",
                                "div[data-challengeinfo] div",
                                "span[data-number]",
                                "span[jsname='V67aGc']",
                                "div.BqLWCe",
                            ]:
                                try:
                                    for el_num in page.query_selector_all(sel):
                                        txt = el_num.inner_text().strip()
                                        if txt.isdigit() and 1 <= len(txt) <= 3:
                                            match_num = txt
                                            break
                                except Exception:
                                    pass
                                if match_num:
                                    break

                            if not match_num:
                                m = re.search(
                                    r"(?:ketuk|tap|pilih|choose|select|angka|nomor)\s*[:\s]*(\d{1,3})\b",
                                    page_text,
                                    re.IGNORECASE,
                                )
                                if m:
                                    match_num = m.group(1)

                            panel_msg = (
                                "[bold yellow]📱 KONFIRMASI VERIFIKASI 2-LANGKAH (2FA) GOOGLE[/bold yellow]\n\n"
                                "Google mengirimkan permintaan verifikasi ke ponsel/perangkat Anda.\n"
                            )
                            if match_num:
                                panel_msg += (
                                    f"[white]Silakan buka ponsel Anda, ketuk [bold green]Ya[/bold green], "
                                    f"dan pilih angka:[/white] [bold gold underline] {match_num} [/bold gold underline]\n"
                                )
                            else:
                                panel_msg += "[white]Silakan buka ponsel Anda dan ketuk [bold green]Ya, itu saya[/bold green].[/white]\n"

                            panel_msg += "\n[muted]Terminal memantau persetujuan secara otomatis...[/muted]"
                            console.print(
                                Panel(panel_msg, box=box.ROUNDED, title="[yellow]Aksi Pengguna Diperlukan[/yellow]")
                            )

                    except Exception:
                        time.sleep(1.5)
                        continue

                    time.sleep(2.0)

            console.print("[error]✗ Waktu tunggu autentikasi habis (melebihi 2 menit).[/error]")
            browser.close()
            return False

        except Exception as err:
            console.print(f"[error]✗ Terjadi kesalahan pada alur otomatisasi:[/error] {err}")
            return False


def launch_interactive_login(
    url: str,
    profile_dir: Optional[Union[Path, str]] = None,
    timeout: int = 300,
) -> bool:
    """Meluncurkan jendela peramban visual (headful) untuk login manual ke situs apa pun.

    Sesi, akun, dan cookie akan disimpan langsung ke profil lokal proyek sasaran
    sehingga terisolasi dan aman untuk proyek tersebut.

    Args:
        url: Alamat website sasaran untuk login.
        profile_dir: Direktori profil peramban sasaran.
        timeout: Batas waktu maksimal jendela dibuka (detik).

    Returns:
        bool: True jika jendela berhasil dibuka dan ditutup dengan aman.
    """
    target_profile = resolve_profile_dir(profile_dir)
    clean_profile_locks(target_profile)
    setup_clean_profile(target_profile, port=2828)

    firefox_bin = get_firefox_executable()
    if not firefox_bin or not firefox_bin.exists():
        console.print("[error]✗ Biner Firefox Portable tidak ditemukan.[/error]")
        return False

    console.print(
        Panel(
            f"[bold cyan]PELUNCURAN SESI LOGIN VISUAL (HEADFUL)[/bold cyan]\n\n"
            f"• Target URL : [cyan]{url}[/cyan]\n"
            f"• Profil     : [yellow]{target_profile}[/yellow]\n\n"
            f"Silakan lakukan login pada jendela Firefox yang terbuka.\n"
            f"Setelah selesai dan Anda menutup jendela, sesi akan tersimpan otomatis di profil proyek ini.",
            box=box.ROUNDED,
            title="[green]Login Interaktif Situs Web[/green]",
        )
    )

    cmd = [
        str(firefox_bin),
        "-no-remote",
        "-profile",
        str(target_profile),
        url,
    ]

    try:
        proc = subprocess.Popen(cmd)
        proc.wait(timeout=timeout)
        clean_profile_locks(target_profile)
        console.print("[success]✓ Sesi login peramban lokal telah disimpan.[/success]")
        return True
    except subprocess.TimeoutExpired:
        proc.terminate()
        clean_profile_locks(target_profile)
        console.print("[warning]⚠ Waktu sesi login interaktif berakhir.[/warning]")
        return False
    except Exception as err:
        console.print(f"[error]✗ Gagal meluncurkan peramban: {err}[/error]")
        return False


def _print_verify_result(res: Dict[str, Any]) -> None:
    """Mencetak panel hasil verifikasi sesi ke terminal."""
    if res.get("success"):
        console.print(
            Panel(
                f"[bold green]✓ SESI WEB AKTIF & TERVERIFIKASI![/bold green]\n\n"
                f"URL Kanvas : [cyan]{res.get('url', '-')}[/cyan]\n"
                f"Judul Tab  : [white]{res.get('title', '-')}[/white]\n\n"
                "[muted]Firefox Portable lokal siap digunakan secara senyap (headless).[/muted]",
                box=box.ROUNDED,
                title="[green]Status Autentikasi Headless[/green]",
            )
        )
    else:
        console.print(
            Panel(
                f"[bold yellow]ℹ SESI AKUN BELUM TERHUBUNG KE PERAMBAN LOKAL[/bold yellow]\n\n"
                f"Kondisi : [white]{res.get('message', 'Sesi belum terpasang.')}[/white]\n"
                f"URL     : [cyan]{res.get('url', '-')}[/cyan]\n\n"
                "[bold green]Langkah Berikutnya:[/bold green] Jalankan `firefox-stealth login` untuk menghubungkan akun Anda.",
                box=box.ROUNDED,
                title="[yellow]Status Sesi Profil[/yellow]",
            )
        )


def main(argv: Optional[List[str]] = None) -> int:
    """Titik masuk CLI autentikasi tunggal (Full CLI)."""
    parser = argparse.ArgumentParser(
        description="Unified Authenticator for Firefox Stealth Automation (Isolated Project Profiles)."
    )
    parser.add_argument(
        "--url",
        type=str,
        default=FLOW_HOME_URL,
        help="URL sasaran untuk login/verifikasi (default: Google Flow)",
    )
    parser.add_argument(
        "--profile-dir",
        type=str,
        default=None,
        help="Direktori profil browser target (default: ./browser_profile)",
    )
    parser.add_argument(
        "--email",
        type=str,
        help="Email akun Google untuk login otomatis",
    )
    parser.add_argument(
        "--password",
        type=str,
        help="Kata sandi akun Google untuk login otomatis",
    )
    parser.add_argument(
        "--interactive",
        action="store_true",
        help="Buka browser visual (headful) untuk login manual ke situs apa pun",
    )
    parser.add_argument(
        "--verify",
        action="store_true",
        help="Uji keabsahan sesi di background tanpa melakukan login baru",
    )

    args = parser.parse_args(argv)

    if args.interactive:
        success = launch_interactive_login(url=args.url, profile_dir=args.profile_dir)
        return 0 if success else 1

    if args.verify:
        console.print(f"[info]ℹ Menguji status sesi untuk {args.url} di latar belakang...[/info]")
        res = verify_session_headless(target_url=args.url, profile_dir=args.profile_dir)
        _print_verify_result(res)
        return 0 if res.get("success") else 1

    success = automated_google_login(
        email=args.email,
        password=args.password,
        profile_dir=args.profile_dir,
        target_url=args.url,
    )
    return 0 if success else 1


if __name__ == "__main__":
    sys.exit(main())
