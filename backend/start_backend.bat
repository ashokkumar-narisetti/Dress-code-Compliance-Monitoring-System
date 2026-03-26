@echo off
echo Starting DressCode Monitor Backend...
cd /d "%~dp0"
venv\Scripts\uvicorn main:app --reload --port 8000
pause
