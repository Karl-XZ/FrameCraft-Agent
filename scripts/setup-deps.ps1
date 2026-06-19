# FrameCraft Agent — 单 Codex agent 新后端依赖安装
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
& $backendPy -m pip install -q --upgrade pip
& $backendPy -m pip install -q -r backend\requirements.txt
$env:PYTHONPATH = "backend"
& $backendPy -c "import app.main; print('OK  single-agent backend deps')"
Write-Host "OK  backend venv" -ForegroundColor Green

Write-Step "Node / HyperFrames deps"
$nodeExe = Resolve-NodeExe
if ($nodeExe) {
    $env:Path = "$(Split-Path $nodeExe);$env:APPDATA\npm;$env:Path"
}
if (Get-Command npm -ErrorAction SilentlyContinue) {
    npm install
    Push-Location framecraft-agent
    npm install
    Pop-Location
} else {
    throw "npm is required on Windows for this setup script."
}

Write-Step "Codex CLI"
$codex = Get-Command codex -ErrorAction SilentlyContinue
if ($codex) {
    & codex --version
} else {
    Write-Host "WARN Codex CLI not found. Install Codex or set CODEX_BIN." -ForegroundColor Yellow
}

Write-Step "Done"
Write-Host "Run scripts\verify-env.ps1 to check all components." -ForegroundColor Gray
