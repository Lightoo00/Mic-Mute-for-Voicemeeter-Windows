@echo off
setlocal
cd /d "%~dp0"
py -m pip install --upgrade pip
py -m pip install -r requirements.txt
if errorlevel 1 (
  echo Dependency installation failed.
  pause
  exit /b 1
)
py -m PyInstaller --noconfirm --clean --onefile --windowed --icon "assets\mic-mute.ico" --add-data "assets\mic-mute.ico;assets" --hidden-import pystray --hidden-import pystray._win32 --name "Mic Mute for Voicemeeter & Windows" main.py
if errorlevel 1 (
  echo Main application build failed.
  pause
  exit /b 1
)
py -m PyInstaller --noconfirm --clean --onefile --windowed --icon "assets\mic-mute.ico" --name MicMuteUpdater updater.py
if errorlevel 1 (
  echo Updater build failed.
  pause
  exit /b 1
)
mkdir release 2>nul
copy /Y "dist\Mic Mute for Voicemeeter & Windows.exe" "release\Mic Mute for Voicemeeter & Windows.exe"
copy /Y "dist\MicMuteUpdater.exe" "release\MicMuteUpdater.exe"
powershell -NoProfile -Command "Compress-Archive -Path 'release\*' -DestinationPath 'Mic-Mute-Windows-v6.2.2.zip' -Force"
echo.
echo Build complete: Mic-Mute-Windows-v6.2.2.zip
pause
