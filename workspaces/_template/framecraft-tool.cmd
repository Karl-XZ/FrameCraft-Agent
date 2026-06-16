@echo off
REM FrameCraft Agent 工具包装器 — 从 workspace 根目录调用
setlocal EnableExtensions
set "WS=%~dp0"
set "BACKEND=%WS%..\..\backend"
set "PY=%BACKEND%\venv\Scripts\python.exe"
cd /d "%BACKEND%"

if exist "%WS%framecraft-env.cmd" call "%WS%framecraft-env.cmd"

if not exist "%PY%" (
  echo {"ok": false, "error": "backend venv python not found"} 1>&2
  exit /b 1
)

"%PY%" -m app.services.agent_tools %*
