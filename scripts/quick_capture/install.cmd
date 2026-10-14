@echo off
rem Double-click: install GTD Quick Capture (starts with Windows + runs now).
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0quick_capture.ps1" -Install
pause
