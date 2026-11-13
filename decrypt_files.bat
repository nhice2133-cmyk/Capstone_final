@echo off
setlocal enabledelayedexpansion
title SMART ENTRY - Biometric & Snapshot Image Decryption Tool
color 0A

:: Resolve absolute project directory without trailing backslash
set "PROJECT_ROOT=%~dp0"
if "%PROJECT_ROOT:~-1%"=="\" set "PROJECT_ROOT=%PROJECT_ROOT:~0,-1%"
cd /d "%PROJECT_ROOT%"

:: Determine Python executable
if exist "%PROJECT_ROOT%\venv\Scripts\python.exe" (
    set "PYTHON_CMD=%PROJECT_ROOT%\venv\Scripts\python.exe"
) else (
    set "PYTHON_CMD=python"
)

:: Verify python is installed
where python >nul 2>nul
if %ERRORLEVEL% NEQ 0 (
    if not exist "%PROJECT_ROOT%\venv\Scripts\python.exe" (
        echo.
        echo ===============================================================================
        echo [ERROR] Python is not installed or not found in system PATH!
        echo ===============================================================================
        echo Please ensure Python 3.10+ is installed and added to your system PATH.
        echo ===============================================================================
        echo.
        pause
        exit /b 1
    )
)

:: Launch the decryption engine (passes any CLI arguments along)
"%PYTHON_CMD%" "%PROJECT_ROOT%\tools\decrypt_tool.py" %*

if %ERRORLEVEL% NEQ 0 (
    echo.
    pause
)
exit /b %ERRORLEVEL%

