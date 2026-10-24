# ==============================================================================
# FIREFOX STEALTH AUTOMATION — 1-CLICK ALL-IN-ONE INSTALLER & BOOTSTRAPPER
# ==============================================================================
# Cara menjalankan langsung dari GitHub:
# irm https://raw.githubusercontent.com/ululazmi18/firefox-stealth-automation/main/install.ps1 | iex
# ==============================================================================

[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$OutputEncoding = [System.Text.Encoding]::UTF8

Write-Host "==============================================================================" -ForegroundColor Cyan
Write-Host " 🔥 FIREFOX STEALTH AUTOMATION — AUTO PROVISIONER & INSTALLER" -ForegroundColor Cyan
Write-Host " Otomasi Deteksi Tool, Dependensi & Penyediaan Browser Stealth Mandiri" -ForegroundColor DarkGray
Write-Host "==============================================================================" -ForegroundColor Cyan
Write-Host ""

function Refresh-EnvPath {
    $env:Path = [System.Environment]::GetEnvironmentVariable("Path","Machine") + ";" + [System.Environment]::GetEnvironmentVariable("Path","User")
}

# 1. PERIKSA ATAU PASANG 7-ZIP
Write-Host "[1/5] Memeriksa ketersediaan 7-Zip..." -ForegroundColor Yellow
$has7z = (Get-Command 7z -ErrorAction SilentlyContinue) -or (Test-Path "C:\Program Files\7-Zip\7z.exe") -or (Test-Path "C:\Program Files (x86)\7-Zip\7z.exe")
if (-not $has7z) {
    Write-Host "      7-Zip belum terpasang. Memasang 7-Zip otomatis via winget..." -ForegroundColor Cyan
    winget install --id 7zip.7zip -e --source winget --accept-source-agreements --accept-package-agreements --silent
    Refresh-EnvPath
}
Write-Host "      ✓ 7-Zip siap digunakan." -ForegroundColor Green

# 2. PERIKSA ATAU PASANG GIT
Write-Host "[2/5] Memeriksa ketersediaan Git..." -ForegroundColor Yellow
$hasGit = Get-Command git -ErrorAction SilentlyContinue
if (-not $hasGit) {
    Write-Host "      Git belum terpasang. Memasang Git otomatis via winget..." -ForegroundColor Cyan
    winget install --id Git.Git -e --source winget --accept-source-agreements --accept-package-agreements --silent
    Refresh-EnvPath
}
Write-Host "      ✓ Git siap digunakan." -ForegroundColor Green

# 3. PERIKSA ATAU PASANG PYTHON
Write-Host "[3/5] Memeriksa ketersediaan Python..." -ForegroundColor Yellow
$pythonCmd = $null
if (Get-Command python -ErrorAction SilentlyContinue) {
    $pythonCmd = "python"
} elseif (Get-Command py -ErrorAction SilentlyContinue) {
    $pythonCmd = "py"
}

if (-not $pythonCmd) {
    Write-Host "      Python belum terpasang. Memasang Python 3.12 otomatis via winget..." -ForegroundColor Cyan
    winget install --id Python.Python.3.12 -e --source winget --accept-source-agreements --accept-package-agreements --silent
    Refresh-EnvPath
    if (Get-Command python -ErrorAction SilentlyContinue) { $pythonCmd = "python" }
}

if (-not $pythonCmd) {
    Write-Host "      ✗ Python tidak dapat ditemukan setelah instalasi. Harap restart terminal Anda." -ForegroundColor Red
    exit 1
}
$pyVer = & $pythonCmd --version
Write-Host "      ✓ Python terdeteksi: $pyVer" -ForegroundColor Green

# 4. KLONING ATAU PINDAH KE DIREKTORI PROYEK
Write-Host "[4/5] Menyiapkan repositori firefox-stealth-automation..." -ForegroundColor Yellow
$repoDir = "firefox-stealth-automation"
if (-not (Test-Path "setup_browser.py")) {
    if (-not (Test-Path $repoDir)) {
        Write-Host "      Mengkloning repositori dari GitHub..." -ForegroundColor Cyan
        git clone https://github.com/ululazmi18/firefox-stealth-automation.git
    }
    Set-Location $repoDir
}
Write-Host "      ✓ Berada di direktori: $(Get-Location)" -ForegroundColor Green

# 5. PASANG DEPENDENSI PIP & JALANKAN SETUP BROWSER
Write-Host "[5/5] Memasang dependensi Python & mengonfigurasi Firefox Portable..." -ForegroundColor Yellow
& $pythonCmd -m pip install -r requirements.txt --quiet
& $pythonCmd setup_browser.py

Write-Host ""
Write-Host "==============================================================================" -ForegroundColor Green
Write-Host " ✓ INSTALASI & BOOTSTRAP FIREFOX STEALTH SELESAI & SIAP DIGUNAKAN!" -ForegroundColor Green
Write-Host "==============================================================================" -ForegroundColor Green
Write-Host " Anda dapat menjalankan audit benchmark anti-bot kapan saja dengan:" -ForegroundColor Cyan
Write-Host " python harness_audit.py --run-id uji_awal" -ForegroundColor Yellow
Write-Host "==============================================================================" -ForegroundColor Green
