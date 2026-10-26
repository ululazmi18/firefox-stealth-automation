# 🔥 Firefox Stealth Automation — Undetected Gecko Automation Framework

[![Python Version](https://img.shields.io/badge/python-3.10%20%7C%203.11%20%7C%203.12-blue.svg)](https://www.python.org/)
[![Browser](https://img.shields.io/badge/browser-Firefox%20Portable%20(Gecko)-orange.svg)](https://portableapps.com/apps/internet/firefox_portable)
[![Protocol](https://img.shields.io/badge/protocol-Marionette%20Socket%20(No%20CDP)-green.svg)](https://firefox-source-docs.mozilla.org/testing/marionette/)
[![License](https://img.shields.io/badge/license-MIT-purple.svg)](LICENSE)
[![Bot Detection](https://img.shields.io/badge/bot%20detection-17%20Benchmarks%20Hardened-success.svg)](REPORT.md)

Framework otomasi peramban mandiri (*standalone*) berbasis **Mozilla Firefox Portable Edition** yang dikeraskan (*hardened*) secara bertahap untuk meminimalkan sinyal deteksi otomasi dan fingerprinting pada **17 situs benchmark deteksi bot terkemuka** (SannySoft, DeviceAndBrowserInfo, Rebrowser, BrowserScan, IPFighter, CreepJS, BrowserLeaks, dll.).

---

## 🎯 Mengapa Firefox Marionette vs Puppeteer/Chromium?

Otomasi berbasis Chromium (Puppeteer, Playwright default, Selenium Chrome) rentan terdeteksi oleh sistem anti-bot modern (Cloudflare, DataDome, Akamai, Kasada) akibat:
1. **Kebocoran Chrome DevTools Protocol (CDP):** Detektor memeriksa `Runtime.enable`, `cdc_` variables, dan objek debugging yang ditinggalkan Chromium.
2. **Flag Universal `navigator.webdriver`:** Selalu bernilai `true` saat dikontrol driver standar.
3. **Kebocoran WebRTC:** STUN candidate membocorkan alamat IP publik dan identitas interface jaringan asli.

### Keunggulan Arsitektur Gecko Stealth Ini:
* **Bebas Kebocoran CDP (100% Passed):** Menggunakan native socket TCP Marionette (`127.0.0.1:2828`). Gecko tidak menggunakan CDP sehingga terbebas dari artefak runtime evaluation Chromium.
* **Neutralisasi `navigator.webdriver`:** WebExtension Stealth Bridge native Gecko menyamarkan `Navigator.prototype.webdriver` menjadi `false` (dengan status `[native code]`, `enumerable: true`, `configurable: true`) pada window utama maupun seluruh dynamic iframe.
* **WebRTC Leak Protection:** Kebocoran IP via STUN dinonaktifkan secara native di level profil peramban.
* **Zero External Drivers:** Tidak memerlukan executable binary `geckodriver.exe` eksternal. Klien Python murni berkomunikasi langsung dengan soket JSON wire protocol Gecko.
* **Portabel & Mandiri:** CLI bootstrapper mengunduh dan mengekstrak Firefox Portable resmi secara otomatis tanpa dialog GUI.

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

## 🚀 Panduan Memulai Cepat (Quickstart)

### ⚡ Cara Termudah: 1 Baris Perintah PowerShell (Otomatis Penuh)
Cukup buka terminal PowerShell dan jalankan **1 baris perintah** berikut:
```powershell
irm https://raw.githubusercontent.com/ululazmi18/firefox-stealth-automation/main/install.ps1 | iex
```
*Skrip ini akan otomatis memeriksa & memasang Python, Git, 7-Zip, mengkloning repositori, memasang pustaka, serta mengunduh dan mengonfigurasi Firefox Portable Edition resmi!*

---

### 🛠️ Pemasangan Manual Langkah demi Langkah (Alternatif)

#### 1. Prasyarat & Pemasangan Dependensi
Pastikan Python 3.10+ telah terpasang. Direkomendasikan memasang **7-Zip** agar proses ekstraksi paket Firefox Portable berjalan 100% otomatis di latar belakang tanpa dialog GUI:
```powershell
# Pasang 7-Zip (jika belum ada di sistem)
winget install 7zip.7zip

# Kloning repositori & pasang pustaka Python
git clone https://github.com/ululazmi18/firefox-stealth-automation.git
cd firefox-stealth-automation
pip install -r requirements.txt
```

#### 2. Bootstrapping Firefox Portable (Satu Baris Perintah)
Jalankan bootstrapper mandiri untuk mengunduh, mengekstrak, dan mengonfigurasi Firefox Portable Edition resmi secara senyap:
```powershell
python setup_browser.py
```
*Skrip ini akan memeriksa ketersediaan biner, mengunduh dari CDN PortableApps resmi (dengan fitur auto-resume & perpanjangan timeout), mengekstraknya menggunakan 7-Zip, dan menyiapkan direktori profil `browser_profile/` yang telah di-hardening anti-deteksi bot.*

### 3. Autentikasi Google Flow Headless (`login.py`)
Hubungkan akun Google langsung dari baris perintah terminal tanpa membuka browser manual:
```powershell
# Jalankan login interaktif Full CLI
python login.py

# Atau sertakan kredensial langsung via argumen CLI
python login.py --email akun@gmail.com --password "KataSandiAnda"
```
*Fitur ini berjalan 100% senyap di latar belakang, menangani prompt 2FA/notifikasi perangkat ponsel, dan mengekspor token sesi langsung ke `browser_profile/cookies.sqlite`.*

### 4. Menjalankan Suite Audit 17 Situs Benchmark
Jalankan harness pengujian untuk memverifikasi jejak otomasi kapan saja:
```powershell
python harness_audit.py --run-id verifikasi_1
```
*Tangkapan layar full-page `.png` dan data JSON dari seluruh 17 situs benchmark akan tersimpan di direktori `reports/verifikasi_1/`.*

---

## 💻 Penggunaan Modul Python (`firefox_stealth`)

Paket `firefox_stealth` dirancang dengan arsitektur modular **Separation of Concerns (SoC)** dan standar kemasan **PEP 517/518/621**. Modul ini menyediakan dua gaya penggunaan: *High-Level Context Manager* (`StealthBrowser`) dan *Low-Level Socket Client* (`MarionetteDriver`).

### 1. Gaya High-Level (`StealthBrowser` — Direkomendasikan)
Mengelola siklus hidup proses peramban, port TCP, handshake, serta penutupan sesi secara otomatis dan bersih (*auto-cleanup*):

```python
from firefox_stealth import StealthBrowser

# Jalankan peramban headless secara senyap
with StealthBrowser(headless=True) as browser:
    # 1. Navigasi ke target web
    browser.navigate("https://bot-detector.rebrowser.net")

    # 2. Periksa status navigasi dan neutralisasi anti-bot
    webdriver_state = browser.execute_script("return navigator.webdriver;")
    page_title = browser.execute_script("return document.title;")
    print(f"Halaman: {page_title} | navigator.webdriver: {webdriver_state}")

    # 3. Tangkap visual viewport dalam format PNG bytes
    screenshot_bytes = browser.take_screenshot()
    with open("hasil_uji.png", "wb") as f:
        f.write(screenshot_bytes)
```

### 2. Gaya Low-Level (`MarionetteDriver`)
Untuk integrasi tingkat lanjut di mana proses peramban dikontrol secara terpisah:

```python
from firefox_stealth import MarionetteDriver

driver = MarionetteDriver(host="127.0.0.1", port=2828)
driver.connect()

# Interaksi elemen tanpa menyentuh kursor fisik OS (Zero Cursor Hijacking)
elem_id = driver.find_element(using="css selector", value="input[name='q']")
driver.send_keys(elem_id, "Firefox Stealth Automation\n")

driver.close()
```

---

## 🌐 Ekosistem & Integrasi Proyek Terkait

`firefox-stealth-automation` berfungsi sebagai fondasi mesin peramban anti-deteksi bot untuk aplikasi hilir (*downstream apps*). 

* 🎨 **[Google Flow Image Generator (image-generator)](https://github.com/ululazmi18/image-generator):**
  Aplikasi otomasi pembuatan gambar AI 100% senyap berbasis Google Flow. `image-generator` memanfaatkan `firefox_stealth.MarionetteDriver` untuk mengirimkan prompt via ProseMirror DOM, memantau kanvas, dan mengunduh hasil gambar 1K tanpa memblokir kursor pengguna.
  
  **Integrasi Berdampingan (Side-by-Side):**
  Cukup letakkan kedua repositori berdampingan dalam satu folder workspace:
  ```text
  workspace/
  ├── firefox-stealth-automation/    # Mesin browser & penyimpanan profil/sesi login
  └── image-generator/               # Aplikasi otomasi generasi gambar
  ```
  `image-generator` secara otomatis mendeteksi biner `firefox_portable` dan sesi login `browser_profile` dari repositori ini tanpa perlu konfigurasi manual!

---

## 📁 Struktur Direktori Repositori

```text
firefox-stealth-automation/
├── firefox_stealth/           # Paket Modul Python Utama (PEP 517/518/621 & SoC)
│   ├── __init__.py            # Titik masuk publik (StealthBrowser, MarionetteDriver, dll.)
│   ├── browser.py             # Pengontrol siklus hidup peramban StealthBrowser
│   ├── driver.py              # Klien soket protokol Marionette JSON Wire native
│   ├── exceptions.py          # Hierarki pengecualian terstruktur (MarionetteError)
│   └── profile.py             # Generator konfigurasi hardening prefs.js & user.js
├── tests/                     # Rangkaian pengujian unit otomatis
│   ├── test_browser.py
│   ├── test_driver.py
│   └── test_profile.py
├── stealth_addon/             # Native Gecko WebExtension Stealth Bridge
│   ├── manifest.json          # Manifest WebExtension V2
│   └── stealth.js             # Injeksi exportFunction/cloneInto di Navigator.prototype
├── pyproject.toml             # Konfigurasi packaging modern PEP 517/518/621
├── setup_browser.py           # CLI bootstrapper installer Firefox Portable otomatis
├── login.py                   # Standalone Full CLI Google Flow & OAuth 2FA login engine
├── harness_audit.py           # QA multi-site benchmark audit suite (17 situs deteksi)
├── REPORT.md                  # Laporan teknis final & analisis empiris komparatif
├── requirements.txt           # Dependensi modul (rich, curl_cffi)
├── LICENSE                    # Lisensi Open Source (MIT)
├── .gitignore                 # Filter proteksi file biner, profil, dan artefak uji
└── README.md                  # Dokumentasi proyek
```

---

## 🛡️ Kebijakan Keamanan & Etika Pengujian

Framework ini dirancang untuk tujuan pengujian jaminan kualitas (**QA Automation**), audit ketahanan peramban terhadap deteksi sidik jari digital (**Fingerprint Hardening**), dan riset ketahanan otomasi. Hanya diuji terhadap 17 situs benchmark deteksi bot resmi. Penulis tidak bertanggung jawab atas penyalahgunaan alat ini di luar tujuan riset dan pengujian yang sah.

---

## 📄 Lisensi

Didistribusikan di bawah lisensi **MIT License**. Lihat [LICENSE](LICENSE) untuk informasi lebih lanjut.
Dibuat oleh [Ulul Azmi](https://github.com/ululazmi18).

