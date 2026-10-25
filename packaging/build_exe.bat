@echo off
setlocal
cd /d "%~dp0\.."
echo === Netsys Monitor: build .exe ===
python -m pip install --upgrade pip
python -m pip install -r requirements-dev.txt
if errorlevel 1 goto :err
python -m netsys_monitor --make-icon netsys.ico
if errorlevel 1 goto :err
pyinstaller --noconfirm --clean packaging\netsys_monitor.spec
if errorlevel 1 goto :err
echo.
echo Selesai: dist\NetsysMonitor.exe
echo SHA-256:
certutil -hashfile dist\NetsysMonitor.exe SHA256
pause
exit /b 0
:err
echo Build gagal. Lihat pesan di atas.
pause
exit /b 1
