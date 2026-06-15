# FrameCraft Agent environment check
# Usage: powershell -ExecutionPolicy Bypass -File scripts/verify-env.ps1

$ErrorActionPreference = "Continue"
$root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)

Write-Host "=== FrameCraft Agent Env Check ===" -ForegroundColor Cyan
Write-Host "Root: $root`n"

$pathsFile = Join-Path $root "config\local.paths.json"
$nodeExe = "C:\Users\ZHOU\AppData\Local\Programs\node-v22.20.0-win-x64\node.exe"
if (Test-Path $pathsFile) {
    $paths = Get-Content $pathsFile -Raw | ConvertFrom-Json
    if ($paths.tools.node_exe -and (Test-Path $paths.tools.node_exe)) {
        $nodeExe = $paths.tools.node_exe
    }
}

if (Test-Path $nodeExe) {
    $nodeVer = & $nodeExe --version
    Write-Host "OK  Node.js $nodeVer" -ForegroundColor Green
    Write-Host "    $nodeExe" -ForegroundColor Gray
} else {
    Write-Host "MISS Node.js" -ForegroundColor Red
}

foreach ($cmd in @("ffmpeg", "python", "git")) {
    $found = Get-Command $cmd -ErrorAction SilentlyContinue
    if ($found) {
        Write-Host "OK  $cmd -> $($found.Source)" -ForegroundColor Green
    } else {
        Write-Host "MISS $cmd" -ForegroundColor Red
    }
}

Write-Host "`n=== Jianying ===" -ForegroundColor Cyan
if (Test-Path $pathsFile) {
    $paths = Get-Content $pathsFile -Raw | ConvertFrom-Json
    foreach ($key in @("app_exe", "draft_dir", "data_dir")) {
        $p = $paths.jianying.$key
        if ($p -and (Test-Path $p)) {
            Write-Host "OK  jianying.$key" -ForegroundColor Green
            Write-Host "    $p" -ForegroundColor Gray
        } elseif ($p) {
            Write-Host "WARN jianying.$key path missing: $p" -ForegroundColor Yellow
        }
    }
    if ($paths.jianying.app_version) {
        Write-Host "INFO version $($paths.jianying.app_version)" -ForegroundColor Gray
    }
}

Write-Host "`n=== HyperFrames ===" -ForegroundColor Cyan
$hfBin = Join-Path $root "node_modules\hyperframes\dist\cli.js"
if (Test-Path $hfBin) {
    $hfVer = & $nodeExe $hfBin --version 2>$null
    Write-Host "OK  hyperframes $hfVer" -ForegroundColor Green
} else {
    Write-Host "MISS hyperframes (npm install hyperframes)" -ForegroundColor Yellow
}

$chromeRel = "chrome\win64-149.0.7827.115\chrome-win64\chrome.exe"
$chromePath = Join-Path $root $chromeRel
if (Test-Path $chromePath) {
    Write-Host "OK  Chromium $chromePath" -ForegroundColor Green
} else {
    Write-Host "WARN Chromium not pre-downloaded (first render will download)" -ForegroundColor Yellow
}

Write-Host "`n=== VectCutAPI ===" -ForegroundColor Cyan
$venvPy = Join-Path $root "vendor\VectCutAPI\venv-capcut\Scripts\python.exe"
if (Test-Path $venvPy) {
    Write-Host "OK  VectCutAPI venv" -ForegroundColor Green
    & $venvPy -c "import flask, requests; print('OK  flask + requests')" 2>&1
} else {
    Write-Host "MISS VectCutAPI venv" -ForegroundColor Red
}

Write-Host "`n=== OpenClaw ===" -ForegroundColor Cyan
$env:Path = (Split-Path $nodeExe) + ";C:\Users\ZHOU\AppData\Roaming\npm;" + $env:Path
$openclaw = Get-Command openclaw -ErrorAction SilentlyContinue
if ($openclaw) {
    $ocVer = & openclaw --version 2>&1
    Write-Host "OK  openclaw $ocVer" -ForegroundColor Green
} else {
    Write-Host "MISS openclaw (npm i -g openclaw@latest, Node>=22.19)" -ForegroundColor Yellow
}

Write-Host "`n=== ASR (faster-whisper) ===" -ForegroundColor Cyan
$asrPy = Join-Path $root "vendor\asr-venv\Scripts\python.exe"
if (Test-Path $asrPy) {
    & $asrPy -c "from faster_whisper import WhisperModel; print('OK  faster-whisper')" 2>&1
} else {
    Write-Host "MISS asr-venv" -ForegroundColor Yellow
}

Write-Host "`n=== Done ===" -ForegroundColor Cyan
