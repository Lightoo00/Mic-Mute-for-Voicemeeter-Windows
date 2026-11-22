@echo off
setlocal
cd /d "%~dp0"
title Mic Mute - Publish release
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0tools\publish.ps1"
echo.
echo Press any key to close this window.
pause >nul
