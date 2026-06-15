@echo off
cd /d "%~dp0.."
python -m venv backend\venv 2>nul
call backend\venv\Scripts\activate
pip install -r backend\requirements.txt -q
uvicorn backend.app.main:app --host 127.0.0.1 --port 8000
