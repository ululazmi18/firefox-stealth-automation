# 🔥 Firefox Stealth Automation — Undetected Gecko Automation Framework

[![Python Version](https://img.shields.io/badge/python-3.10%20%7C%203.11%20%7C%203.12-blue.svg)](https://www.python.org/)
[![Browser](https://img.shields.io/badge/browser-Firefox%20Portable%20(Gecko)-orange.svg)](https://portableapps.com/apps/internet/firefox_portable)
[![Protocol](https://img.shields.io/badge/protocol-Marionette%20Socket%20(No%20CDP)-green.svg)](https://firefox-source-docs.mozilla.org/testing/marionette/)
[![License](https://img.shields.io/badge/license-MIT-purple.svg)](LICENSE)
[![Bot Detection](https://img.shields.io/badge/bot%20detection-17%20Benchmarks%20Hardened-success.svg)](REPORT.md)
[![Package Ready](https://img.shields.io/badge/package-pip%20installable-brightgreen.svg)](pyproject.toml)

Framework otomasi peramban mandiri (*standalone*) berbasis **Mozilla Firefox Portable Edition** yang dikeraskan (*hardened*) secara native untuk meminimalkan sinyal deteksi otomasi dan fingerprinting pada **17 situs benchmark deteksi bot terkemuka** (SannySoft, DeviceAndBrowserInfo, Rebrowser, BrowserScan, IPFighter, CreepJS, BrowserLeaks, dll.).

Dilengkapi dengan **sistem isolasi profil browser privat per-proyek** (*Project-Isolated Profiles*), memungkinkan penyimpanan sesi, login akun Google/web, dan cookies tersimpan aman di direktori lokal masing-masing proyek tanpa saling mencemari atau bercampur dengan proyek lainnya di direktori mana pun.

---

## 🎯 Mengapa Firefox Marionette vs Puppeteer/Chromium?

Otomasi berbasis Chromium (Puppeteer, Playwright default, Selenium Chrome) rentan terdeteksi oleh sistem anti-bot modern (Cloudflare, DataDome, Akamai, Kasada) akibat:
1. **Kebocoran Chrome DevTools Protocol (CDP):** Detektor memeriksa `Runtime.enable`, `cdc_` variables, dan objek debugging yang ditinggalkan Chromium.
2. **Flag Universal `navigator.webdriver`:** Selalu bernilai `true` saat dikontrol driver standar.
3. **Kebocoran WebRTC:** STUN candidate membocorkan alamat IP publik dan identitas interface jaringan asli.

### Keunggulan Arsitektur Gecko Stealth Ini:
* **Bebas Kebocoran CDP (100% Passed):** Menggunakan native socket TCP Marionette (`127.0.0.1:2828`). Gecko tidak menggunakan CDP sehingga terbebas dari artefak runtime evaluation Chromium.
* **Neutralisasi `navigator.webdriver`:** WebExtension Stealth Bridge native Gecko menyamarkan `Navigator.prototype.webdriver` menjadi `false` (dengan status `[native code]`, `enumerable: true`, `configurable: true`) pada window utama maupun seluruh dynamic iframe.
* **Isolasi Profil Privat per Proyek:** Setiap proyek memiliki direktori `browser_profile` lokalnya sendiri. Token sesi dan cookie tersimpan terisolasi di folder proyek pemanggil.
* **Zero External Drivers:** Tidak memerlukan executable binary `geckodriver.exe` eksternal. Klien Python murni berkomunikasi langsung dengan soket JSON wire protocol Gecko.
* **Self-Healing Locks:** Otomatis mendeteksi dan membersihkan berkas lockfile yatim (`parent.lock`) dari sesi crash tanpa memicu galat "Firefox is already running".

---

## 📊 Hasil Audit Benchmark (Sebelum vs Sesudah)

Berdasarkan pengujian empiris 3x run berturut-turut pada 17 situs benchmark bot detection (baca laporan teknis lengkap di [REPORT.md](REPORT.md)):

| No | Situs Benchmark | Sebelum Hardening | Pasca Hardening | Status Hasil |
| :---: | :--- | :---: | :---: | :---: |
| 1 | **[SannySoft Bot Test](https://bot.sannysoft.com)** | Gagal (2 checks merah) | **PASSED** (WebDriver New hijau) | **HIJAU** |
| 2 | **[Device & Browser Info](https://deviceandbrowserinfo.com/are_you_a_bot)** | Gagal (100% Robot Terdeteksi) | **PASSED** (0 Failed signals) | **HIJAU** |
| 3 | **[Rebrowser Bot Detector](https://bot-detector.rebrowser.net)** | Gagal (`navigatorWebdriver: true`) | **CLEAN** (`🟢 No webdriver presented`) | **HIJAU** |
| 4 | **[BrowserScan Bot Detection](https://www.browserscan.net/id/bot-detection)** | Gagal (Robot Flag Merah) | **PASSED** (Robot label hilang) | **HIJAU** |
| 5 | **[IP Fighter Bot Detection](https://ipfighter.com/bot-detection)** | 98% Human (1 Flagged Issue) | **100% Clean** (0 Issues) | **HIJAU** |
| 6 | **[CreepJS Deep Fingerprinting](https://abrahamjuliot.github.io/creepjs/)** | Webdriver aktif; IP STUN bocor | **PASSED** (Webdriver dinetralkan, STUN blocked) | **HIJAU** |
| 7 | **[BrowserLeaks WebRTC Leak](https://browserleaks.com/webrtc)** | BOCOR (IP Publik Terbaca) | **NO LEAK** (WebRTC Disabled / No Leak) | **HIJAU** |
| 8–17 | **10 Situs Benchmark Lainnya** | Stabil | **100% Stabil (Zero Regression)** | **STABIL** |

---

## 📦 Pemasangan Modul Python (Siap Pakai di Proyek Mana Pun)

Modul ini telah mengadopsi standar **PEP 517/518/621** (`pyproject.toml`) dan dapat dipasang langsung ke lingkungan Python lokal:

### 1. Pemasangan Mode Editable (Lokal Pengembang)
```bash
cd firefox-stealth-automation
pip install -e .
```
Atau menggunakan `uv`:
```bash
uv pip install -e .
```

### 2. Pemasangan Langsung dari Git URL
```bash
pip install git+https://github.com/ululazmi18/firefox-stealth-automation.git
```

---

## 🛠️ CLI Terpadu: `firefox-stealth`

Setelah dipasang, perintah CLI `firefox-stealth` aktif di terminal sistem:

```bash
# 1. Hubungkan akun Google (Google Flow / Web) Full CLI ke profil lokal proyek
firefox-stealth login --email akun@gmail.com --password "KataSandi"

# 2. Buka browser visual (headful) untuk login manual ke situs apa pun
firefox-stealth login --url "https://twitter.com/login" --interactive

# 3. Uji keabsahan sesi login di background (headless)
firefox-stealth login --verify

# 4. Meluncurkan browser stealth pada port tertentu (misal port 2829)
firefox-stealth launch --url "https://bot.sannysoft.com" --headful --port 2829

# 5. Kelola profil dan periksa cookies yang tersimpan
firefox-stealth profile --action info
firefox-stealth profile --action cookies --domain google
firefox-stealth profile --action clean   # Bersihkan lockfile yatim parent.lock

# 6. Siapkan biner Firefox Portable resmi
firefox-stealth setup
```

---

## 💻 Penggunaan sebagai Modul Python (`firefox_stealth`)

### 1. Peluncuran Browser dengan Isolasi Profil Lokal Proyek (`StealthBrowser`)
Secara default, `StealthBrowser` menggunakan folder `browser_profile` di direktori proyek aktif tempat skrip dieksekusi:

```python
from firefox_stealth import StealthBrowser

# Profil akan dibuat dan disimpan di ./browser_profile (proyek lokal)
with StealthBrowser(headless=True) as browser:
    browser.driver.navigate("https://bot-detector.rebrowser.net")
    print(f"Judul: {browser.driver.title}")
    print(f"Webdriver Flag: {browser.driver.execute_script('return navigator.webdriver;')}")
    
    # Tangkap visual viewport dalam format bytes PNG
    screenshot = browser.driver.take_screenshot()
    with open("hasil.png", "wb") as f:
        f.write(screenshot)
```

### 2. Autentikasi Mandiri & Pengelolaan Cookie Terisolasi
```python
from firefox_stealth import (
    automated_google_login,
    verify_session_headless,
    read_profile_cookies,
    resolve_profile_dir,
)

# 1. Jalankan login otomatis Full CLI ke Google
success = automated_google_login(
    email="akun@gmail.com",
    password="kata_sandi",
    target_url="https://flow.google.com/",
)

# 2. Verifikasi status sesi di latar belakang
status = verify_session_headless()
print("Status Sesi:", status["message"])

# 3. Baca cookie akun yang tersimpan secara aman
profile_dir = resolve_profile_dir()
cookies = read_profile_cookies(profile_dir, domain_filter="google")
print(f"Ditemukan {len(cookies)} cookie Google tersimpan.")
```

---

## 🌐 Ekosistem & Integrasi Proyek Terkait

`firefox-stealth-automation` berfungsi sebagai fondasi peramban anti-deteksi bot untuk aplikasi hilir (*downstream apps*):

* 🎨 **[Google Flow Image Generator (image-generator)](https://github.com/ululazmi18/image-generator):**
  Aplikasi otomasi pembuatan gambar AI 100% senyap berbasis Google Flow. `image-generator` secara otomatis mengimpor `from firefox_stealth import MarionetteDriver` dari paket ini dan menggunakan profil lokal proyek tanpa tumpang tindih dengan proyek lain.
  
  **Struktur Penempatan Berdampingan di `D:\Tools`:**
  ```text
  D:\Tools/
  ├── firefox-stealth-automation/    # Mesin browser stealth & utilitas CLI
  ├── image-generator/               # Aplikasi otomasi pembuatan gambar AI
  └── setup_tools_dan_mcp.ps1        # Otomasi sinkronisasi toolchain terpusat
  ```

---

## 📁 Struktur Direktori Repositori

```text
firefox-stealth-automation/
├── firefox_stealth/           # Paket Modul Python Utama (PEP 517/518/621 & SoC)
│   ├── __init__.py            # Titik masuk publik (StealthBrowser, MarionetteDriver, auth, dll.)
│   ├── auth.py                # Mesin autentikasi Google Flow, Full CLI & interactive login
│   ├── browser.py             # Pengontrol siklus hidup peramban StealthBrowser & biner
│   ├── cli.py                 # Titik masuk CLI terpadu `firefox-stealth`
│   ├── driver.py              # Klien soket protokol Marionette JSON Wire native
│   ├── exceptions.py          # Hierarki pengecualian terstruktur (MarionetteError)
│   ├── profile.py             # Isolasi profil per-proyek, cookie vault, & self-healing locks
│   └── stealth_addon/         # Salinan bundle WebExtension Stealth Bridge
├── tests/                     # Rangkaian pengujian unit otomatis (19 tests)
│   ├── test_cli.py            # Pengujian utilitas CLI
│   ├── test_driver_logic.py   # Pengujian Marionette protocol logic
│   ├── test_exceptions.py     # Pengujian hierarki exception
│   ├── test_profile.py        # Pengujian inisialisasi user.js & cookies
│   └── test_profile_isolation.py # Pengujian isolasi profil per-proyek & self-healing locks
├── stealth_addon/             # Native Gecko WebExtension Stealth Bridge
│   ├── manifest.json          # Manifest WebExtension V2
│   └── stealth.js             # Injeksi exportFunction/cloneInto di Navigator.prototype
├── pyproject.toml             # Konfigurasi packaging modern PEP 517/518/621 & CLI script
├── setup_browser.py           # Bootstrapper installer Firefox Portable otomatis
├── login.py                   # Backward-compatible CLI Google Flow authenticator
├── harness_audit.py           # QA multi-site benchmark audit suite (17 situs deteksi)
├── REPORT.md                  # Laporan teknis final & analisis empiris komparatif
├── requirements.txt           # Dependensi modul (rich, curl_cffi, playwright)
├── LICENSE                    # Lisensi Open Source (MIT)
├── .gitignore                 # Filter proteksi file biner, profil, dan artefak uji
└── README.md                  # Dokumentasi proyek
```

---

## 📄 Lisensi
Didistribusikan di bawah lisensi **MIT License**. Lihat [LICENSE](LICENSE) untuk informasi lebih lanjut.  
Dibuat oleh [Ulul Azmi](https://github.com/ululazmi18).
