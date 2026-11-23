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

echo.
echo [1/4] Building the single-file EXE (auto-update package) ...
py -m PyInstaller --noconfirm --clean --onefile --windowed --icon "assets\mic-mute.ico" ^
  --add-data "assets\mic-mute.ico;assets" ^
  --hidden-import pystray --hidden-import pystray._win32 ^
  --collect-all sounddevice ^
  --name "Mic Mute for Voicemeeter & Windows" main.py
if errorlevel 1 (
  echo Main application build failed.
  pause
  exit /b 1
)

echo.
echo [2/4] Building the fast-start folder build ...
py -m PyInstaller --noconfirm --clean --windowed --icon "assets\mic-mute.ico" ^
  --add-data "assets\mic-mute.ico;assets" ^
  --hidden-import pystray --hidden-import pystray._win32 ^
  --collect-all sounddevice ^
  --distpath dist-fast --workpath build-fast ^
  --name "Mic Mute for Voicemeeter & Windows" main.py
if errorlevel 1 (
  echo Fast build failed.
  pause
  exit /b 1
)

echo.
echo [3/4] Building the updater ...
py -m PyInstaller --noconfirm --clean --onefile --windowed --icon "assets\mic-mute.ico" --name MicMuteUpdater updater.py
if errorlevel 1 (
  echo Updater build failed.
  pause
  exit /b 1
)

echo.
echo [4/4] Packaging ...
mkdir release 2>nul
copy /Y "dist\Mic Mute for Voicemeeter & Windows.exe" "release\Mic Mute for Voicemeeter & Windows.exe"
copy /Y "dist\MicMuteUpdater.exe" "release\MicMuteUpdater.exe"
copy /Y "dist\MicMuteUpdater.exe" "dist-fast\Mic Mute for Voicemeeter & Windows\MicMuteUpdater.exe"
powershell -NoProfile -Command "Compress-Archive -Path 'release\*' -DestinationPath 'Mic-Mute-Windows-v7.0.3.zip' -Force"
powershell -NoProfile -Command "Compress-Archive -Path 'dist-fast\Mic Mute for Voicemeeter & Windows\*' -DestinationPath 'Mic-Mute-Fast-v6.2.2.zip' -Force"
echo.
echo Build complete:
echo   Mic-Mute-Windows-v7.0.3.zip   (auto-update package)
echo   Mic-Mute-Fast-v6.2.2.zip      (fast-start folder build)
pause
