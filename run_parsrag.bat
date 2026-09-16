@echo off
title ParsRAG System Launcher
echo ===================================================
echo           Starting ParsRAG Air-Gapped Assistant
echo ===================================================
echo.

:: Check for virtualenv
if exist .\.venv\Scripts\python.exe (
    echo [INFO] Activating virtual environment...
    set PYTHON_CMD=.\.venv\Scripts\python.exe
) else (
    echo [INFO] Using system Python...
    set PYTHON_CMD=python
)

:: Launch browser in background after 2 seconds
start "" cmd /c "timeout /t 2 /nobreak >nul && start http://localhost:8000"

:: Run FastAPI Uvicorn Server
echo [INFO] Starting local FastAPI server on http://localhost:8000...
%PYTHON_CMD% -m uvicorn backend.main:app --host 0.0.0.0 --port 8000
pause
