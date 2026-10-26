"""CUSTOM EXCEPTION HIERARCHY — FIREFOX STEALTH AUTOMATION.

Modul ini mendefinisikan hierarki kelas eksepsi terstruktur dan spesifik
untuk menangani seluruh galat protokol Marionette, koneksi TCP, timeout,
dan eksekusi otomasi browser Gecko.
"""

from typing import Any, Optional


class MarionetteException(Exception):
    """Kelas dasar untuk seluruh eksepsi yang dihasilkan oleh Marionette driver."""

    def __init__(self, message: str, details: Optional[Any] = None) -> None:
        super().__init__(message)
        self.message = message
        self.details = details

    def __str__(self) -> str:
        if self.details:
            return f"{self.message} (Rincian: {self.details})"
        return self.message


class MarionetteConnectionError(MarionetteException):
    """Terjadi ketika koneksi TCP ke soket Marionette terputus atau gagal terhubung."""
    pass


class MarionetteTimeoutError(MarionetteException):
    """Terjadi ketika operasi soket atau penantian kondisi (wait) melampaui batas waktu."""
    pass


class MarionetteProtocolError(MarionetteException):
    """Terjadi ketika respons dari Gecko Marionette mengembalikan kode galat JSON W3C."""
    pass


class NoSuchElementException(MarionetteProtocolError):
    """Terjadi saat elemen web sasaran tidak ditemukan di halaman aktif."""
    pass


class ScriptExecutionError(MarionetteProtocolError):
    """Terjadi saat evaluasi kode JavaScript di halaman web mengalami galat runtime."""
    pass


class BrowserProcessError(MarionetteException):
    """Terjadi saat proses biner Firefox gagal diluncurkan atau terhenti mendadak."""
    pass
