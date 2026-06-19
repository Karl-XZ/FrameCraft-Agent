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

Write-Host "`n=== Backend ===" -ForegroundColor Cyan
$backendPy = Join-Path $root "backend\venv\Scripts\python.exe"
if (Test-Path $backendPy) {
    $env:PYTHONPATH = "backend"
    & $backendPy -c "import app.main; print('OK  single-agent backend')" 2>&1
} else {
    Write-Host "MISS backend venv" -ForegroundColor Red
}

Write-Host "`n=== Codex ===" -ForegroundColor Cyan
$codex = Get-Command codex -ErrorAction SilentlyContinue
if ($codex) {
    & codex --version
} else {
    Write-Host "MISS codex" -ForegroundColor Yellow
}

Write-Host "`n=== Done ===" -ForegroundColor Cyan
