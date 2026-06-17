# FrameCraft Agent — 一键安装 Python/ASR/OpenClaw 网关等运行时依赖
# Usage: powershell -ExecutionPolicy Bypass -File scripts/setup-deps.ps1

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
Set-Location $root

function Write-Step($msg) { Write-Host "`n=== $msg ===" -ForegroundColor Cyan }

function Resolve-NodeExe {
    $pathsFile = Join-Path $root "config\local.paths.json"
    if (Test-Path $pathsFile) {
        $paths = Get-Content $pathsFile -Raw | ConvertFrom-Json
        if ($paths.tools.node_exe -and (Test-Path $paths.tools.node_exe)) {
            return $paths.tools.node_exe
        }
    }
    $candidates = @(
        "$env:USERPROFILE\.proto\bin\node.exe",
        "$env:LOCALAPPDATA\Programs\node-v22.20.0-win-x64\node.exe",
        "C:\nodejs\node.exe"
    )
    foreach ($c in $candidates) {
        if (Test-Path $c) {
            $ver = & $c --version 2>$null
            if ($ver -match '^v22\.') { return $c }
        }
    }
    return (Get-Command node -ErrorAction SilentlyContinue).Source
}

Write-Step "Backend Python venv"
$backendPy = Join-Path $root "backend\venv\Scripts\python.exe"
if (-not (Test-Path $backendPy)) {
    python -m venv backend\venv
}
& $backendPy -m pip install -q -r backend\requirements.txt
& $backendPy -m pip install -q -r vendor\VectCutAPI\requirements.txt
& $backendPy -c "import oss2, flask; print('OK  VectCutAPI deps (oss2, flask)')"
Write-Host "OK  backend venv" -ForegroundColor Green

Write-Step "ASR (faster-whisper)"
$asrPy = Join-Path $root "vendor\asr-venv\Scripts\python.exe"
if (-not (Test-Path $asrPy)) {
    python -m venv vendor\asr-venv
}
& $asrPy -m pip install -q -r vendor\asr-requirements.txt
& $asrPy -c "from faster_whisper import WhisperModel; print('OK  faster-whisper')"

Write-Step "OpenClaw gateway auth (mode=none)"
$nodeExe = Resolve-NodeExe
if ($nodeExe) {
    $env:Path = "$(Split-Path $nodeExe);$env:APPDATA\npm;$env:Path"
}
$openclaw = Get-Command openclaw -ErrorAction SilentlyContinue
if ($openclaw) {
    $patch = Join-Path $root "config\openclaw.gateway.patch.json"
    & openclaw config patch --file $patch 2>&1 | Out-Null
    Write-Host "OK  openclaw gateway.auth.mode=none" -ForegroundColor Green
} else {
    Write-Host "WARN openclaw not found; skip gateway patch (npm i -g openclaw@latest)" -ForegroundColor Yellow
}

Write-Step "Done"
Write-Host "Run scripts\verify-env.ps1 to check all components." -ForegroundColor Gray
