"""FIREFOX STEALTH AUTOMATION — GOOGLE & WEB AUTHENTICATOR (FULL CLI).

Titik masuk kompatibilitas mundur (backward-compatibility wrapper) untuk
menghubungkan sesi akun ke dalam profil Firefox Portable lokal secara 100% Full CLI.
Mendelegasikan eksekusi ke modul inti `firefox_stealth.auth`.
"""

import sys
from pathlib import Path

# Pastikan modul internal firefox_stealth dapat diimpor langsung
_pkg_root = Path(__file__).resolve().parent
if str(_pkg_root) not in sys.path:
    sys.path.insert(0, str(_pkg_root))

from firefox_stealth.auth import main

if __name__ == "__main__":
    sys.exit(main())
