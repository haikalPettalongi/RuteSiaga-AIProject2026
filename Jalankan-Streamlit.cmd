@echo off
cd /d "%~dp0"
set "PYTHON_RUTESIAGA=%~dp0..\RuteSiaga_RUNTIME_LOKAL\.venv\Scripts\python.exe"
if not exist "%PYTHON_RUTESIAGA%" set "PYTHON_RUTESIAGA=%~dp0.venv\Scripts\python.exe"
if not exist "%PYTHON_RUTESIAGA%" (
 echo Lingkungan Python belum ada. Jalankan Siapkan-Python.cmd terlebih dahulu.
 pause
 exit /b 1
)
"%PYTHON_RUTESIAGA%" -m streamlit run streamlit_app.py
if errorlevel 1 pause
