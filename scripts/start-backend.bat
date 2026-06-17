@echo off
cd /d "%~dp0.."
call "%~dp0setup-deps.bat"
if errorlevel 1 exit /b 1
echo [FrameCraft] Starting backend with venv Python on http://127.0.0.1:8000
backend\venv\Scripts\python.exe -m uvicorn backend.app.main:app --host 127.0.0.1 --port 8000 --reload
