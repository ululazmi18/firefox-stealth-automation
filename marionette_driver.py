"""MARIONETTE STEALTH DRIVER — NATIVE GECKO AUTOMATION BRIDGE.

Klien soket native Marionette untuk mengontrol Mozilla Firefox Portable Edition
secara senyap dan tidak terdeteksi (Undetected Stealth Automation).
Berkomunikasi langsung melalui protokol Marionette JSON Wire Protocol over TCP,
menginjeksi WebExtension Stealth Bridge secara transparan saat inisialisasi sesi,
dan meniadakan ketergantungan pada binary geckodriver eksternal.
"""

import base64
import json
import socket
import time
import zipfile
from pathlib import Path
from typing import Any, Dict, List, Optional


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

    def __init__(self, host: str = "127.0.0.1", port: int = 2828):
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

        Langkah inisialisasi:
        1. Menghubungkan ke 127.0.0.1:port via TCP.
        2. Menerima paket handshake pembuka dari Firefox Gecko.
        3. Mengirimkan perintah 'WebDriver:NewSession'.
        4. Mengatur konteks Marionette ke 'content' (halaman web DOM).
        5. Menginjeksi WebExtension stealth secara otomatis via 'Addon:Install'.

        Args:
            timeout (float): Waktu tunggu koneksi dalam detik.

        Returns:
            str: ID sesi Marionette (session_id).

        Raises:
            ConnectionError: Jika peramban tidak merespons atau soket terputus.
            RuntimeError: Jika inisialisasi sesi ditolak oleh Gecko.
        """
        self.sock = socket.create_connection((self.host, self.port), timeout=timeout)
        self.sock.settimeout(timeout)

        # 1. Baca panjang header handshake
        hs_len = b""
        while True:
            ch = self.sock.recv(1)
            if ch == b":":
                break
            hs_len += ch
        self.sock.recv(int(hs_len.decode("ascii")))

        # 2. Inisialisasi sesi baru
        res = self.send("WebDriver:NewSession", {})
        self.session_id = res.get("sessionId")

        # 3. Set konteks ke content
        self.send("Marionette:SetContext", {"value": "content"})

        # 4. Injeksi WebExtension stealth native Gecko
        self._install_stealth_addon()

        return self.session_id

    def _install_stealth_addon(self) -> None:
        """Mengompilasi dan menginstal WebExtension stealth secara otomatis ke sesi Marionette."""
        addon_dir = Path(__file__).resolve().parent / "stealth_addon"
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
            # Lanjutkan eksekusi jika instalasi addon gagal agar tidak memblokir driver
            pass

    def send(self, name: str, parameters: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Mengirimkan paket perintah berformat Marionette JSON wire protocol ke peramban.

        Args:
            name (str): Nama perintah Marionette (misal: 'WebDriver:Navigate').
            parameters (dict | None): Parameter pendukung untuk perintah tersebut.

        Returns:
            dict: Respons payload hasil eksekusi dari Gecko.

        Raises:
            RuntimeError: Jika Gecko mengembalikan pesan galat.
            ConnectionError: Jika koneksi terputus saat membaca respons.
        """
        if not self.sock:
            raise RuntimeError("Koneksi soket Marionette belum dibuka. Panggil connect() terlebih dahulu.")

        self.msg_id += 1
        payload = json.dumps([0, self.msg_id, name, parameters or {}])
        msg = f"{len(payload)}:{payload}".encode("utf-8")
        self.sock.sendall(msg)

        # Baca panjang respons berformat <length>:
        length_bytes = b""
        while True:
            c = self.sock.recv(1)
            if not c:
                raise ConnectionError("Koneksi terputus saat membaca respons peramban.")
            if c == b":":
                break
            length_bytes += c

        total_length = int(length_bytes.decode("ascii"))
        received_data = b""
        while len(received_data) < total_length:
            chunk = self.sock.recv(min(4096, total_length - len(received_data)))
            if not chunk:
                break
            received_data += chunk

        raw_resp = json.loads(received_data.decode("utf-8"))
        if raw_resp[2] is not None:
            raise RuntimeError(f"Kesalahan Marionette [{name}]: {raw_resp[2]}")
        return raw_resp[3]

    def navigate(self, url: str) -> None:
        """Membuka alamat URL di tab browser yang aktif.

        Args:
            url (str): Alamat web lengkap (misal 'https://bot.sannysoft.com').
        """
        self.send("WebDriver:Navigate", {"url": url})

    def execute_script(self, script: str, args: Optional[List[Any]] = None) -> Any:
        """Mengeksekusi kode JavaScript langsung di dalam konteks halaman web aktif.

        Args:
            script (str): Kode JavaScript (dapat menyertakan 'return').
            args (list | None): Argumen yang diteruskan ke JavaScript via array 'arguments'.

        Returns:
            any: Nilai kembalian hasil evaluasi skrip.
        """
        res = self.send("WebDriver:ExecuteScript", {"script": script, "args": args or []})
        return res.get("value")

    def find_element(self, using: str, value: str) -> str:
        """Mencari elemen web di halaman aktif dan mengembalikan ID elemen string W3C.

        Args:
            using (str): Strategi pencarian elemen ('css selector', 'xpath', 'tag name', 'link text').
            value (str): Nilai pemilih/selector elemen.

        Returns:
            str: ID string unik elemen web W3C untuk interaksi klik/ketik.
        """
        res = self.send("WebDriver:FindElement", {"using": using, "value": value})
        val = res.get("value", {})
        return val.get("element-6066-11e4-a52e-4f735466cecf") or list(val.values())[0]

    def element_click(self, element_id: str) -> None:
        """Mengirimkan event klik native Gecko ke elemen web sasaran.

        Args:
            element_id (str): ID elemen W3C yang diperoleh dari find_element().
        """
        self.send("WebDriver:ElementClick", {"id": element_id})

    def element_send_keys(self, element_id: str, text: str) -> None:
        """Mengirimkan rentetan pengetikan teks ke elemen input sasaran.

        Args:
            element_id (str): ID elemen W3C input field.
            text (str): Teks yang akan dimasukkan ke field.
        """
        self.send("WebDriver:ElementSendKeys", {"id": element_id, "text": text})

    def take_screenshot(self, full: bool = False) -> bytes:
        """Mengambil tangkapan layar halaman web aktif dan mengembalikan data biner PNG.

        Args:
            full (bool): Jika True, mengambil tangkapan layar full-page dari atas ke bawah.
                         Jika False, mengambil tangkapan layar area viewport yang tampak.

        Returns:
            bytes: Data biner gambar berekstensi PNG.
        """
        res = self.send("WebDriver:TakeScreenshot", {"full": full})
        b64_data = res.get("value", "")
        return base64.b64decode(b64_data)

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
