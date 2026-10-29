"""FIREFOX STEALTH AUTOMATION — COMMAND LINE INTERFACE (CLI).

Menyediakan utilitas CLI terpadu `firefox-stealth` untuk:
- Mengelola login akun dan sesi privat terisolasi per-proyek.
- Meluncurkan peramban stealth (headful/headless) dengan port fleksibel.
- Menginspeksi status profil, cookie vault, dan pembersihan lockfile.
- Menyiapkan instalasi biner peramban portable secara mandiri.
"""

import argparse
import sys
import time
from pathlib import Path
from typing import List, Optional

from rich import box
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from firefox_stealth import __version__
from firefox_stealth.auth import (
    automated_google_login,
    launch_interactive_login,
    verify_session_headless,
)
from firefox_stealth.browser import StealthBrowser, get_firefox_executable
from firefox_stealth.profile import (
    clean_profile_locks,
    get_profile_summary,
    read_profile_cookies,
    resolve_profile_dir,
    setup_clean_profile,
)

console = Console()


def handle_login(args: argparse.Namespace) -> int:
    """Menangani subperintah `login`."""
    target_profile = resolve_profile_dir(args.profile_dir)

    if args.interactive:
        success = launch_interactive_login(url=args.url, profile_dir=target_profile)
        return 0 if success else 1

    if args.verify:
        console.print(f"[cyan]ℹ Menguji status sesi untuk [bold]{args.url}[/bold] di profil: {target_profile}[/cyan]")
        res = verify_session_headless(target_url=args.url, profile_dir=target_profile)
        if res.get("success"):
            console.print(
                Panel(
                    f"[bold green]✓ SESI AKTIF & TERVERIFIKASI![/bold green]\n\n"
                    f"URL   : [cyan]{res.get('url')}[/cyan]\n"
                    f"Judul : [white]{res.get('title')}[/white]\n"
                    f"Pesan : [dim]{res.get('message')}[/dim]",
                    box=box.ROUNDED,
                    title="[green]Status Autentikasi[/green]",
                )
            )
            return 0
        else:
            console.print(
                Panel(
                    f"[bold yellow]ℹ AKUN BELUM TERHUBUNG[/bold yellow]\n\n"
                    f"Kondisi : [white]{res.get('message')}[/white]\n"
                    f"URL     : [cyan]{res.get('url', '-')}[/cyan]\n\n"
                    "[bold green]Langkah Berikutnya:[/bold green] Jalankan `firefox-stealth login` untuk masuk.",
                    box=box.ROUNDED,
                    title="[yellow]Status Sesi Profil[/yellow]",
                )
            )
            return 1

    success = automated_google_login(
        email=args.email,
        password=args.password,
        profile_dir=target_profile,
        target_url=args.url,
    )
    return 0 if success else 1


def handle_launch(args: argparse.Namespace) -> int:
    """Menangani subperintah `launch`."""
    target_profile = resolve_profile_dir(args.profile_dir)
    headless = not args.headful

    console.print(
        Panel(
            f"[bold cyan]MELUNCURKAN FIREFOX STEALTH BROWSER[/bold cyan]\n\n"
            f"• Mode        : [bold {'yellow' if headless else 'green'}]{'Headless' if headless else 'Headful (Visual)'}[/]\n"
            f"• Port        : [cyan]{args.port}[/cyan]\n"
            f"• Profil      : [yellow]{target_profile}[/yellow]\n"
            f"• Target URL  : [cyan]{args.url or '(Halaman Awal)'}[/cyan]",
            box=box.ROUNDED,
            title="[cyan]Stealth Browser Launcher[/cyan]",
        )
    )

    try:
        with StealthBrowser(
            profile_dir=target_profile,
            port=args.port,
            headless=headless,
        ) as browser:
            if args.url:
                browser.driver.navigate(args.url)
                console.print(f"[success]✓ Halaman berhasil dimuat:[/success] [cyan]{browser.driver.url}[/cyan]")
                console.print(f"[dim]Judul Halaman: {browser.driver.title}[/dim]")

            if not headless:
                console.print("\n[dim]Peramban aktif. Tekan Ctrl+C di terminal untuk menutup sesi peramban...[/dim]")
                try:
                    while True:
                        time.sleep(1)
                except KeyboardInterrupt:
                    console.print("\n[yellow]Menutup peramban secara anggun...[/yellow]")
        console.print("[success]✓ Sesi peramban selesai dan ditutup dengan aman.[/success]")
        return 0
    except Exception as err:
        console.print(f"[error]✗ Terjadi galat saat meluncurkan peramban:[/error] {err}")
        return 1


def handle_profile(args: argparse.Namespace) -> int:
    """Menangani subperintah `profile`."""
    target_profile = resolve_profile_dir(args.profile_dir)
    action = args.action

    if action == "init":
        setup_clean_profile(target_profile, port=args.port)
        console.print(f"[success]✓ Profil bersih berhasil diinisialisasi di:[/success] [cyan]{target_profile}[/cyan]")
        return 0

    if action == "clean":
        cleaned = clean_profile_locks(target_profile)
        if cleaned:
            console.print(f"[success]✓ Lockfile yatim (parent.lock) berhasil dibersihkan di:[/success] [cyan]{target_profile}[/cyan]")
        else:
            console.print(f"[info]ℹ Profil tidak memiliki lockfile yatim: [cyan]{target_profile}[/cyan][/info]")
        return 0

    if action == "cookies":
        cookies = read_profile_cookies(target_profile, domain_filter=args.domain)
        if not cookies:
            console.print(f"[yellow]Tidak ada cookie tersimpan di:[/yellow] [cyan]{target_profile}[/cyan]")
            return 0

        table = Table(title=f"Cookie Vault ({target_profile.name})", box=box.ROUNDED)
        table.add_column("Domain", style="cyan")
        table.add_column("Name", style="green")
        table.add_column("Value (Snippet)", style="white")
        table.add_column("Path", style="dim")
        table.add_column("Secure", style="magenta")

        for c in cookies[:30]:
            val_snippet = c["value"][:25] + "..." if len(c["value"]) > 25 else c["value"]
            table.add_row(
                c["domain"],
                c["name"],
                val_snippet,
                c["path"],
                str(c["secure"]),
            )
        console.print(table)
        if len(cookies) > 30:
            console.print(f"[dim]Menampilkan 30 dari total {len(cookies)} cookies.[/dim]")
        return 0

    # Default: info
    summary = get_profile_summary(target_profile)
    table = Table(title="Informasi Profil Browser Lokal Proyek", box=box.ROUNDED)
    table.add_column("Parameter", style="cyan")
    table.add_column("Nilai", style="white")

    table.add_row("Lokasi Direktori", summary["profile_dir"])
    table.add_row("Status Direktori", "[green]Ada[/green]" if summary["exists"] else "[red]Belum Ada[/red]")
    table.add_row("Konfigurasi user.js", "[green]Hardened[/green]" if summary["has_user_js"] else "[yellow]Belum Terpasang[/yellow]")
    table.add_row("Basis Data Cookies", "[green]Aktif[/green]" if summary["has_cookies"] else "[yellow]Kosong[/yellow]")
    table.add_row("Total Cookie", str(summary["cookie_count"]))
    table.add_row("Lock Status", "[red]Terkunci (parent.lock)[/red]" if summary["locked"] else "[green]Bebas[/green]")
    if summary["domains"]:
        table.add_row("Domain Terhubung", ", ".join(summary["domains"][:6]) + ("..." if len(summary["domains"]) > 6 else ""))

    console.print(table)
    return 0


def handle_setup(args: argparse.Namespace) -> int:
    """Menangani subperintah `setup`."""
    target_dir = Path(args.target_dir).resolve() if args.target_dir else None
    ff = get_firefox_executable(portable_dir=target_dir)
    if ff and ff.exists():
        console.print(f"[success]✓ Firefox Portable sudah terpasang dan siap:[/success] [cyan]{ff}[/cyan]")
        return 0

    console.print("[info]Memulai proses bootstrap instalasi Firefox Portable...[/info]")
    pkg_root = Path(__file__).resolve().parent.parent
    setup_script = pkg_root / "setup_browser.py"
    if setup_script.exists():
        import subprocess
        proc = subprocess.run([sys.executable, str(setup_script)])
        return proc.returncode
    else:
        console.print("[error]✗ Skrip bootstrap setup_browser.py tidak ditemukan.[/error]")
        return 1


def main(argv: Optional[List[str]] = None) -> int:
    """Titik masuk utama CLI firefox-stealth."""
    parser = argparse.ArgumentParser(
        prog="firefox-stealth",
        description="Firefox Stealth Automation — Gecko Anti-Bot Engine & Project-Isolated Browser Profile Suite.",
    )
    parser.add_argument(
        "--version",
        action="version",
        version=f"%(prog)s {__version__}",
    )

    subparsers = parser.add_subparsers(dest="command", help="Perintah yang tersedia")

    # 1. Subperintah: login
    p_login = subparsers.add_parser("login", help="Hubungkan akun (Google Flow / Web) ke profil lokal proyek")
    p_login.add_argument("--url", type=str, default="https://flow.google.com/", help="URL sasaran (default: Google Flow)")
    p_login.add_argument("--profile-dir", type=str, default=None, help="Direktori profil sasaran (default: ./browser_profile)")
    p_login.add_argument("--email", type=str, help="Email akun Google untuk login otomatis")
    p_login.add_argument("--password", type=str, help="Kata sandi akun Google")
    p_login.add_argument("--interactive", action="store_true", help="Buka jendela browser headful untuk login manual")
    p_login.add_argument("--verify", action="store_true", help="Uji keabsahan sesi di latar belakang tanpa login baru")
    p_login.set_defaults(func=handle_login)

    # 2. Subperintah: launch
    p_launch = subparsers.add_parser("launch", help="Luncurkan peramban Firefox Stealth via Marionette")
    p_launch.add_argument("--url", type=str, default=None, help="URL yang akan langsung dibuka")
    p_launch.add_argument("--profile-dir", type=str, default=None, help="Direktori profil browser")
    p_launch.add_argument("--port", type=int, default=2828, help="Port Marionette (default: 2828)")
    p_launch.add_argument("--headful", action="store_true", help="Jalankan dalam mode visual dengan GUI peramban")
    p_launch.set_defaults(func=handle_launch)

    # 3. Subperintah: profile
    p_profile = subparsers.add_parser("profile", help="Kelola dan inspeksi profil browser lokal proyek")
    p_profile.add_argument("--profile-dir", type=str, default=None, help="Direktori profil sasaran")
    p_profile.add_argument("--action", choices=["info", "init", "clean", "cookies"], default="info", help="Aksi profil")
    p_profile.add_argument("--port", type=int, default=2828, help="Port Marionette untuk inisialisasi user.js")
    p_profile.add_argument("--domain", type=str, default=None, help="Filter domain saat memeriksa cookies")
    p_profile.set_defaults(func=handle_profile)

    # 4. Subperintah: setup
    p_setup = subparsers.add_parser("setup", help="Unduh dan siapkan biner Firefox Portable resmi")
    p_setup.add_argument("--target-dir", type=str, default=None, help="Direktori tujuan instalasi firefox_portable")
    p_setup.set_defaults(func=handle_setup)

    args = parser.parse_args(argv)

    if not args.command:
        # Tampilkan ringkasan status sistem jika dipanggil tanpa argumen
        target_profile = resolve_profile_dir()
        ff_bin = get_firefox_executable()
        console.print(
            Panel(
                f"[bold cyan]FIREFOX STEALTH AUTOMATION v{__version__}[/bold cyan]\n"
                f"Framework otomasi peramban Gecko anti-deteksi dengan isolasi profil lokal proyek.\n\n"
                f"• Biner Firefox : [cyan]{ff_bin or '[red]Belum Ditemukan[/red]'}[/cyan]\n"
                f"• Profil Aktif  : [yellow]{target_profile}[/yellow]\n\n"
                f"Gunakan [bold white]firefox-stealth --help[/bold white] untuk melihat seluruh perintah CLI.",
                box=box.ROUNDED,
                title="[green]System Overview[/green]",
            )
        )
        return 0

    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
