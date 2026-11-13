@echo off
setlocal EnableDelayedExpansion
title SMART ENTRY - Setup Wizard ^& System Installer
cd /d "%~dp0"

echo ===============================================================================
echo      CARAGA STATE UNIVERSITY CABADBARAN CAMPUS (CSUCC) - ATHENAEUM LIBRARY
echo      SMART ENTRY: Launching Graphical Setup Wizard...
echo ===============================================================================

:: Restore executable if disguised for cloud / Google Drive transfer
if exist "%~dp0Smart_Entry_Setup.bin" (
    if not exist "%~dp0Smart_Entry_Setup.exe" (
        ren "%~dp0Smart_Entry_Setup.bin" Smart_Entry_Setup.exe >nul 2>nul
    )
)

:: 1. Launch the standalone compiled executable if present
if exist "%~dp0Smart_Entry_Setup.exe" (
    start "" "%~dp0Smart_Entry_Setup.exe"
    exit /b 0
)

:: 2. Fallback to host Python
where python >nul 2>nul
if %ERRORLEVEL% EQU 0 (
    start "" python setup_wizard.py
    exit /b 0
)

echo.
echo [!] Setup executable not found and Python is not in PATH.
echo Please install Python 3.10+ and check "Add Python to PATH".
echo.
pause
exit /b 1

