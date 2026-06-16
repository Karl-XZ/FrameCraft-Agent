@echo off
REM FrameCraft Agent 工具包装器 — 从 workspace 根目录调用
setlocal EnableExtensions
set "WS=%~dp0"
set "BACKEND=%WS%..\..\backend"
cd /d "%BACKEND%"
if not defined FRAMECRAFT_PROJECT_ID (
  for /f "usebackq delims=" %%i in (`"%BACKEND%\venv\Scripts\python.exe" -c "import json,pathlib;print(json.loads(pathlib.Path(r'%WS%STATE.json').read_text(encoding='utf-8'))['project_id'])"`) do set "FRAMECRAFT_PROJECT_ID=%%i"
)
if not defined FRAMECRAFT_JOB_ID (
  for /f "usebackq delims=" %%i in (`"%BACKEND%\venv\Scripts\python.exe" -c "import json,pathlib;p=pathlib.Path(r'%WS%STATE.json');d=json.loads(p.read_text(encoding='utf-8'));print(d.get('job_id') or '')"`) do set "FRAMECRAFT_JOB_ID=%%i"
)
"%BACKEND%\venv\Scripts\python.exe" -m app.services.agent_tools %*
