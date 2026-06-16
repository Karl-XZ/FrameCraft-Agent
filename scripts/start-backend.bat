@echo off
cd /d "%~dp0.."
if not exist backend\venv\Scripts\python.exe (
  python -m venv backend\venv
)
call backend\venv\Scripts\activate
pip install -r backend\requirements.txt -q
echo [FrameCraft] Starting backend with venv Python on http://127.0.0.1:8000
backend\venv\Scripts\python.exe -m uvicorn backend.app.main:app --host 127.0.0.1 --port 8000 --reload
