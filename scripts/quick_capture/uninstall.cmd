@echo off
rem Double-click: remove GTD Quick Capture from startup and stop it.
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0quick_capture.ps1" -Uninstall
pause
