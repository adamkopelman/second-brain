@echo off
rem Double-click: run GTD Quick Capture now (tray icon), without installing it.
start "" powershell -NoProfile -STA -WindowStyle Hidden -ExecutionPolicy Bypass -File "%~dp0quick_capture.ps1"
