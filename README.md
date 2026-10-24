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

### 1. Kloning Repositori & Pasang Dependensi
```powershell
git clone https://github.com/ululazmi18/firefox-stealth-automation.git
cd firefox-stealth-automation
pip install -r requirements.txt
```

### 2. Bootstrapping Firefox Portable (Satu Baris Perintah)
Jalankan bootstrapper mandiri untuk mengunduh, mengekstrak, dan mengonfigurasi Firefox Portable Edition resmi secara senyap:
```powershell
python setup_browser.py
```
*Skrip ini akan memeriksa ketersediaan biner, mengunduh dari CDN PortableApps jika belum ada, dan menyiapkan direktori profil `browser_profile/` dengan WebRTC hardening.*

### 3. Menjalankan Suite Audit 17 Situs Benchmark
Jalankan harness pengujian untuk memverifikasi jejak otomasi kapan saja:
```powershell
python harness_audit.py --run-id verifikasi_1
```
*Tangkapan layar full-page `.png` dan data JSON dari seluruh 17 situs benchmark akan tersimpan di direktori `reports/verifikasi_1/`.*

---

## 💻 Penggunaan Driver Python (`marionette_driver.py`)

Gunakan modul `MarionetteDriver` untuk mengontrol peramban secara senyap dalam skrip otomasi Anda sendiri:

```python
import subprocess
import time
from pathlib import Path
from marionette_driver import MarionetteDriver

# 1. Jalankan Firefox Portable (Headless atau GUI)
ff_bin = Path("firefox_portable/App/Firefox64/firefox.exe")
profile_dir = Path("browser_profile")

cmd = [
    str(ff_bin),
    "-no-remote",
    "-headless",         # Hapus argumen ini jika ingin melihat jendela browser
    "-marionette",
    "-profile",
    str(profile_dir),
]
proc = subprocess.Popen(cmd)

time.sleep(2)  # Tunggu port 2828 siap

# 2. Hubungkan driver (Otomatis menginjeksi stealth WebExtension bridge)
driver = MarionetteDriver(host="127.0.0.1", port=2828)
driver.connect()

# 3. Navigasi & Interaksi Web
driver.navigate("https://bot-detector.rebrowser.net")
time.sleep(4)

# 4. Evaluasi Status Stealth
result = driver.execute_script("""
return {
    webdriver: navigator.webdriver,
    title: document.title
};
""")
print("Status Otomasi:", result)  # {'webdriver': False, 'title': '...'}

# 5. Ambil Screenshot
png_bytes = driver.take_screenshot(full=False)
Path("screenshot.png").write_bytes(png_bytes)

# 6. Tutup Sesi
driver.close()
proc.terminate()
```

---

## 📁 Struktur Direktori Repositori

```text
firefox-stealth-automation/
├── stealth_addon/             # Native Gecko WebExtension Stealth Bridge
│   ├── manifest.json          # Manifest WebExtension V2
│   └── stealth.js             # Injeksi exportFunction/cloneInto di Navigator.prototype
├── marionette_driver.py       # Klien Python murni Marionette Wire Protocol
├── setup_browser.py           # CLI bootstrapper installer Firefox Portable otomatis
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
