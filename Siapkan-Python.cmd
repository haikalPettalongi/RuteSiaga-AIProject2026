@echo off
cd /d "%~dp0"
set "VENV_RUTESIAGA=%~dp0..\RuteSiaga_RUNTIME_LOKAL\.venv"
py -3 -m venv "%VENV_RUTESIAGA%"
if errorlevel 1 goto gagal
"%VENV_RUTESIAGA%\Scripts\python.exe" -m pip install -r requirements.txt
if errorlevel 1 goto gagal
echo Siap. Buka Jalankan-Web.cmd.
pause
exit /b 0
:gagal
echo Pemasangan gagal. Periksa Python dan koneksi internet.
pause
exit /b 1
