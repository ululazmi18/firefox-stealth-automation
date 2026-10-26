"""MARIONETTE STEALTH DRIVER — CORE PROTOCOL CLIENT.

Modul klien native Marionette tingkat produksi untuk mengontrol Mozilla Firefox
secara senyap, tanpa CDP leaks, dengan dukungan penuh penanganan jendela/popup,
pengelolaan cookie, eksekusi skrip, dan penantian kondisi (wait until).
"""

import base64
import json
import socket
import time
import zipfile
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, TypeVar

from firefox_stealth.exceptions import (
    MarionetteConnectionError,
    MarionetteException,
    MarionetteProtocolError,
    MarionetteTimeoutError,
    NoSuchElementException,
    ScriptExecutionError,
)

T = TypeVar("T")


class MarionetteDriver:
    """Klien protokol native Marionette untuk Firefox Portable dengan proteksi stealth.

    Menghubungkan kontrol otomasi langsung ke port Marionette Firefox tanpa Chrome DevTools Protocol (CDP),
    sehingga kebal terhadap CDP evaluation leaks, dan menginjeksi WebExtension stealth untuk
    menetralkan 'navigator.webdriver = false' di seluruh window utama dan dynamic iframe.

    Attributes:
        host (str): Alamat IP host peramban (default: '127.0.0.1').
        port (int): Nomor port Marionette yang aktif (default: 2828).
        sock (socket.socket | None): Soket koneksi TCP aktif.
        msg_id (int): Penomoran ID pesan berurutan untuk JSON wire protocol.
        session_id (str | None): ID sesi W3C WebDriver yang sedang aktif di Gecko.
    """

    def __init__(self, host: str = "127.0.0.1", port: int = 2828) -> None:
        """Inisialisasi klien MarionetteDriver.

        Args:
            host (str): Alamat host (default '127.0.0.1').
            port (int): Port Marionette (default 2828).
        """
        self.host = host
        self.port = port
        self.sock: Optional[socket.socket] = None
        self.msg_id = 0
        self.session_id: Optional[str] = None

    def __enter__(self) -> "MarionetteDriver":
        """Dukungan context manager untuk inisialisasi otomatis."""
        if not self.sock:
            self.connect()
        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        """Penutupan aman otomatis saat keluar dari blok context manager."""
        self.close()

    def is_port_open(self, timeout: float = 0.8) -> bool:
        """Memeriksa apakah port Marionette peramban sudah siap menerima koneksi TCP.

        Args:
            timeout (float): Waktu tunggu maksimal pengujian port dalam detik.

        Returns:
            bool: True jika port terbuka dan peramban siap, False jika port tertutup.
        """
        try:
            with socket.create_connection((self.host, self.port), timeout=timeout):
                return True
        except (OSError, socket.timeout):
            return False

    def connect(self, timeout: float = 30.0) -> str:
        """Membuka koneksi soket TCP ke Firefox, melakukan handshake, dan membuat sesi baru.

        Args:
            timeout (float): Waktu tunggu koneksi dalam detik.

        Returns:
            str: ID sesi Marionette (session_id).

        Raises:
            MarionetteConnectionError: Jika peramban tidak merespons atau koneksi gagal.
            MarionetteProtocolError: Jika pembuatan sesi ditolak oleh Gecko.
        """
        try:
            self.sock = socket.create_connection((self.host, self.port), timeout=timeout)
            self.sock.settimeout(timeout)
        except (OSError, socket.timeout) as exc:
            raise MarionetteConnectionError(
                f"Gagal menghubungkan ke Marionette pada {self.host}:{self.port}", details=str(exc)
            ) from exc

        # 1. Baca panjang header handshake Gecko
        hs_len = b""
        try:
            while True:
                ch = self.sock.recv(1)
                if not ch:
                    raise MarionetteConnectionError("Koneksi terputus saat membaca handshake awal.")
                if ch == b":":
                    break
                hs_len += ch
            length = int(hs_len.decode("ascii"))
            self._recv_exact(length)
        except (ValueError, OSError) as exc:
            self.close()
            raise MarionetteConnectionError("Handshake protokol Marionette tidak valid", details=str(exc)) from exc

        # 2. Inisialisasi sesi baru
        res = self.send("WebDriver:NewSession", {})
        if isinstance(res, dict):
            self.session_id = res.get("sessionId")
        else:
            self.session_id = str(res)

        # 3. Set konteks ke content (DOM)
        self.send("Marionette:SetContext", {"value": "content"})

        # 4. Injeksi WebExtension stealth native Gecko
        self._install_stealth_addon()

        return self.session_id or ""

    def _recv_exact(self, total_bytes: int) -> bytes:
        """Membaca sejumlah byte tertentu secara utuh dari soket TCP."""
        if not self.sock:
            raise MarionetteConnectionError("Soket tidak terhubung.")
        data = bytearray()
        while len(data) < total_bytes:
            chunk = self.sock.recv(min(4096, total_bytes - len(data)))
            if not chunk:
                raise MarionetteConnectionError("Koneksi TCP terputus di tengah penerimaan data.")
            data.extend(chunk)
        return bytes(data)

    def _install_stealth_addon(self) -> None:
        """Mengompilasi dan menginstal WebExtension stealth secara otomatis ke sesi Marionette."""
        # Cari direktori stealth_addon baik di root proyek maupun di modul
        candidates = [
            Path(__file__).resolve().parent.parent / "stealth_addon",
            Path(__file__).resolve().parent / "stealth_addon",
        ]
        addon_dir = next((d for d in candidates if d.exists()), None)
        if not addon_dir:
            return

        manifest_file = addon_dir / "manifest.json"
        if not manifest_file.exists():
            return

        xpi_path = addon_dir / "stealth_addon.xpi"
        try:
            with zipfile.ZipFile(xpi_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
                for item in addon_dir.iterdir():
                    if item.name.endswith(".xpi"):
                        continue
                    if item.is_file():
                        zf.write(item, item.name)

            self.send("Addon:Install", {"path": str(xpi_path.resolve()), "temporary": True})
        except Exception:
            # Kegagalan instalasi ekstensi tidak boleh memblokir driver
            pass

    def send(self, name: str, parameters: Optional[Dict[str, Any]] = None) -> Any:
        """Mengirimkan paket perintah berformat Marionette JSON wire protocol ke peramban.

        Args:
            name (str): Nama perintah Marionette (misal: 'WebDriver:Navigate').
            parameters (dict | None): Parameter pendukung untuk perintah tersebut.

        Returns:
            Any: Respons payload hasil eksekusi dari Gecko.

        Raises:
            MarionetteConnectionError: Jika koneksi terputus.
            MarionetteProtocolError / NoSuchElementException / ScriptExecutionError: Jika respons error.
        """
        if not self.sock:
            raise MarionetteConnectionError("Koneksi soket Marionette belum dibuka. Panggil connect() terlebih dahulu.")

        self.msg_id += 1
        payload = json.dumps([0, self.msg_id, name, parameters or {}])
        msg = f"{len(payload)}:{payload}".encode("utf-8")

        try:
            self.sock.sendall(msg)

            # Baca panjang respons berformat <length>:
            length_bytes = b""
            while True:
                c = self.sock.recv(1)
                if not c:
                    raise MarionetteConnectionError("Koneksi terputus saat membaca respons peramban.")
                if c == b":":
                    break
                length_bytes += c

            total_length = int(length_bytes.decode("ascii"))
            received_bytes = self._recv_exact(total_length)
        except (OSError, socket.timeout) as exc:
            self.close()
            raise MarionetteConnectionError(f"Kegagalan I/O soket saat mengirim {name}", details=str(exc)) from exc

        raw_resp = json.loads(received_bytes.decode("utf-8"))
        err = raw_resp[2]
        if err is not None:
            err_msg = str(err.get("message") if isinstance(err, dict) else err)
            err_type = str(err.get("error") if isinstance(err, dict) else "")

            if "no such element" in err_type.lower() or "no such element" in err_msg.lower():
                raise NoSuchElementException(f"Elemen tidak ditemukan pada [{name}]: {err_msg}", details=err)
            if "javascript error" in err_type.lower() or "javascript error" in err_msg.lower():
                raise ScriptExecutionError(f"Galat JavaScript pada [{name}]: {err_msg}", details=err)
            raise MarionetteProtocolError(f"Kesalahan Marionette [{name}]: {err_msg}", details=err)

        return raw_resp[3]

    # ==========================================================================
    # MANAJEMEN JENDELA, TAB & POPUP
    # ==========================================================================

    @property
    def window_handles(self) -> List[str]:
        """Daftar seluruh ID handle jendela/tab yang sedang terbuka di peramban."""
        res = self.send("WebDriver:GetWindowHandles", {})
        if isinstance(res, list):
            return res
        if isinstance(res, dict):
            return res.get("value", [])
        return []

    @property
    def current_window_handle(self) -> str:
        """ID handle jendela/tab yang sedang aktif saat ini."""
        res = self.send("WebDriver:GetWindowHandle", {})
        if isinstance(res, dict):
            return res.get("value", "")
        return str(res or "")

    def switch_to_window(self, handle: str) -> None:
        """Beralih fokus kendali ke jendela atau tab tertentu berdasarkan handle ID.

        Args:
            handle (str): ID handle sasaran dari window_handles.
        """
        self.send("WebDriver:SwitchToWindow", {"handle": handle})

    def close_window(self) -> None:
        """Menutup jendela atau tab yang sedang aktif."""
        self.send("WebDriver:CloseWindow", {})

    def new_window(self, type_hint: str = "tab") -> str:
        """Membuka jendela atau tab baru dan mengembalikan ID handle-nya.

        Args:
            type_hint (str): 'tab' untuk tab baru, atau 'window' untuk jendela baru.

        Returns:
            str: ID handle jendela baru.
        """
        res = self.send("WebDriver:NewWindow", {"type": type_hint})
        if isinstance(res, dict):
            return res.get("handle", "")
        return str(res or "")

    # ==========================================================================
    # NAVIGASI & STATUS HALAMAN
    # ==========================================================================

    def navigate(self, url: str) -> None:
        """Membuka alamat URL di tab browser yang aktif.

        Args:
            url (str): Alamat web lengkap (misal 'https://bot.sannysoft.com').
        """
        self.send("WebDriver:Navigate", {"url": url})

    def refresh(self) -> None:
        """Memuat ulang (reload/refresh) halaman aktif saat ini."""
        self.send("WebDriver:Refresh", {})

    def back(self) -> None:
        """Kembali ke halaman sebelumnya dalam riwayat peramban (back)."""
        self.send("WebDriver:Back", {})

    def forward(self) -> None:
        """Maju ke halaman berikutnya dalam riwayat peramban (forward)."""
        self.send("WebDriver:Forward", {})

    @property
    def current_url(self) -> str:
        """Alamat URL lengkap halaman yang sedang aktif."""
        res = self.send("WebDriver:GetCurrentURL", {})
        if isinstance(res, dict):
            return res.get("value", "")
        return str(res or "")

    @property
    def title(self) -> str:
        """Judul dokumen (title) halaman web yang sedang aktif."""
        res = self.send("WebDriver:GetTitle", {})
        if isinstance(res, dict):
            return res.get("value", "")
        return str(res or "")

    @property
    def page_source(self) -> str:
        """Kode sumber HTML lengkap dari dokumen aktif."""
        res = self.send("WebDriver:GetPageSource", {})
        if isinstance(res, dict):
            return res.get("value", "")
        return str(res or "")

    # ==========================================================================
    # EVALUASI SKRIP & INTERAKSI ELEMEN
    # ==========================================================================

    def execute_script(self, script: str, args: Optional[List[Any]] = None) -> Any:
        """Mengeksekusi kode JavaScript langsung di dalam konteks halaman web aktif.

        Args:
            script (str): Kode JavaScript (dapat menyertakan 'return').
            args (list | None): Argumen yang diteruskan ke JavaScript via array 'arguments'.

        Returns:
            Any: Nilai kembalian hasil evaluasi skrip.
        """
        res = self.send("WebDriver:ExecuteScript", {"script": script, "args": args or []})
        if isinstance(res, dict) and "value" in res:
            return res["value"]
        return res

    def execute_async_script(self, script: str, args: Optional[List[Any]] = None) -> Any:
        """Mengeksekusi kode JavaScript asinkron dengan callback penyelesaian."""
        res = self.send("WebDriver:ExecuteAsyncScript", {"script": script, "args": args or []})
        if isinstance(res, dict) and "value" in res:
            return res["value"]
        return res

    def find_element(self, using: str, value: str) -> str:
        """Mencari elemen web di halaman aktif dan mengembalikan ID elemen string W3C.

        Args:
            using (str): Strategi pencarian elemen ('css selector', 'xpath', 'tag name', 'link text').
            value (str): Nilai pemilih/selector elemen.

        Returns:
            str: ID string unik elemen web W3C untuk interaksi klik/ketik.
        """
        res = self.send("WebDriver:FindElement", {"using": using, "value": value})
        val = res.get("value", {}) if isinstance(res, dict) else res
        if isinstance(val, dict):
            return val.get("element-6066-11e4-a52e-4f735466cecf") or list(val.values())[0]
        return str(val)

    def find_elements(self, using: str, value: str) -> List[str]:
        """Mencari seluruh elemen web yang cocok dan mengembalikan daftar ID elemen W3C.

        Args:
            using (str): Strategi pencarian elemen ('css selector', 'xpath', dll.).
            value (str): Nilai pemilih/selector.

        Returns:
            List[str]: Kumpulan ID elemen string W3C.
        """
        res = self.send("WebDriver:FindElements", {"using": using, "value": value})
        items = res.get("value", []) if isinstance(res, dict) else res
        results: List[str] = []
        if isinstance(items, list):
            for it in items:
                if isinstance(it, dict):
                    el_id = it.get("element-6066-11e4-a52e-4f735466cecf") or list(it.values())[0]
                    results.append(el_id)
                elif isinstance(it, str):
                    results.append(it)
        return results

    def element_click(self, element_id: str) -> None:
        """Mengirimkan event klik native Gecko ke elemen web sasaran."""
        self.send("WebDriver:ElementClick", {"id": element_id})

    def element_send_keys(self, element_id: str, text: str) -> None:
        """Mengirimkan rentetan pengetikan teks ke elemen input sasaran."""
        self.send("WebDriver:ElementSendKeys", {"id": element_id, "text": text})

    def element_clear(self, element_id: str) -> None:
        """Mengosongkan teks pada elemen input sasaran."""
        self.send("WebDriver:ElementClear", {"id": element_id})

    def element_text(self, element_id: str) -> str:
        """Mendapatkan teks terlihat yang terkandung dalam elemen sasaran."""
        res = self.send("WebDriver:GetElementText", {"id": element_id})
        if isinstance(res, dict):
            return res.get("value", "")
        return str(res or "")

    def element_attribute(self, element_id: str, name: str) -> Optional[str]:
        """Mendapatkan nilai atribut HTML tertentu dari elemen sasaran."""
        res = self.send("WebDriver:GetElementAttribute", {"id": element_id, "name": name})
        if isinstance(res, dict):
            return res.get("value")
        return res

    # ==========================================================================
    # MANAJEMEN COOKIES W3C
    # ==========================================================================

    def get_cookies(self) -> List[Dict[str, Any]]:
        """Mendapatkan seluruh cookie yang aktif untuk dokumen halaman saat ini."""
        res = self.send("WebDriver:GetCookies", {})
        if isinstance(res, dict):
            return res.get("value", [])
        return res if isinstance(res, list) else []

    def add_cookie(self, cookie: Dict[str, Any]) -> None:
        """Menambahkan cookie baru ke sesi halaman saat ini."""
        self.send("WebDriver:AddCookie", {"cookie": cookie})

    def delete_all_cookies(self) -> None:
        """Menghapus seluruh cookie yang tersimpan untuk dokumen halaman aktif."""
        self.send("WebDriver:DeleteAllCookies", {})

    # ==========================================================================
    # TANGKAPAN LAYAR & UTILITAS
    # ==========================================================================

    def take_screenshot(self, full: bool = False) -> bytes:
        """Mengambil tangkapan layar halaman web aktif dan mengembalikan data biner PNG.

        Args:
            full (bool): Jika True, mengambil tangkapan layar full-page dari atas ke bawah.
                         Jika False, mengambil tangkapan layar area viewport yang tampak.

        Returns:
            bytes: Data biner gambar berekstensi PNG.
        """
        res = self.send("WebDriver:TakeScreenshot", {"full": full})
        b64_data = res.get("value", "") if isinstance(res, dict) else res
        return base64.b64decode(b64_data)

    def wait_until(
        self,
        predicate: Callable[["MarionetteDriver"], T],
        timeout: float = 10.0,
        poll_interval: float = 0.5,
        message: str = "",
    ) -> T:
        """Menunggu hingga suatu fungsi kondisi bernilai truthy atau batas waktu habis.

        Args:
            predicate: Fungsi callable yang menerima MarionetteDriver dan mengembalikan nilai.
            timeout: Batas waktu maksimal penantian dalam detik.
            poll_interval: Frekuensi polling pemeriksaan dalam detik.
            message: Pesan rincian jika waktu tunggu habis.

        Returns:
            T: Nilai kembalian dari predicate saat bernilai truthy.

        Raises:
            MarionetteTimeoutError: Jika predicate tidak terpenuhi dalam batas waktu.
        """
        end_time = time.time() + timeout
        last_exception: Optional[Exception] = None

        while time.time() < end_time:
            try:
                res = predicate(self)
                if res:
                    return res
            except Exception as exc:
                last_exception = exc
            time.sleep(poll_interval)

        err_msg = message or f"Kondisi tidak terpenuhi setelah {timeout} detik."
        if last_exception:
            err_msg += f" (Galat terakhir: {last_exception})"
        raise MarionetteTimeoutError(err_msg)

    def close(self) -> None:
        """Menutup koneksi soket ke peramban dan menghapus referensi sesi."""
        try:
            if self.session_id and self.sock:
                self.send("WebDriver:DeleteSession", {})
        except Exception:
            pass
        finally:
            if self.sock:
                try:
                    self.sock.close()
                except Exception:
                    pass
                self.sock = None
            self.session_id = None
