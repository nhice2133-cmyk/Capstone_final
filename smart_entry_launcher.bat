@echo off
setlocal EnableDelayedExpansion
title SMART ENTRY: A Face Recognition-Based Attendance and Security Surveillance Kiosk System For The CSUCC Library
color 0A

:: Resolve absolute project directory without trailing backslash
set "PROJECT_ROOT=%~dp0"
if "%PROJECT_ROOT:~-1%"=="\" set "PROJECT_ROOT=%PROJECT_ROOT:~0,-1%"
cd /d "%PROJECT_ROOT%"

:: Determine Python executable (virtualenv or system)
if exist "%PROJECT_ROOT%\venv\Scripts\python.exe" (
    set "PYTHON_CMD=%PROJECT_ROOT%\venv\Scripts\python.exe"
    set "PYTHONW_CMD=%PROJECT_ROOT%\venv\Scripts\pythonw.exe"
) else (
    set "PYTHON_CMD=python"
    set "PYTHONW_CMD=pythonw"
)

:: Check for direct command switches (e.g. from Desktop shortcut)
if "%~1"=="--wizard" goto run_wizard
if "%~1"=="--setup" goto run_wizard
if "%~1"=="--kiosk" goto direct_kiosk
if "%~1"=="--admin" goto direct_admin
if "%~1"=="--tray" goto direct_tray
if "%~1"=="--stop" goto stop_server
if "%~1"=="--server" goto server_only
if "%~1"=="--reset-admin" goto reset_pw

:menu
cls
echo ===============================================================================
echo      CARAGA STATE UNIVERSITY CABADBARAN CAMPUS (CSUCC) - ATHENAEUM LIBRARY
echo      SMART ENTRY: Facial Biometric Attendance & Surveillance Kiosk
echo ===============================================================================
echo.
echo   [0] Launch Graphical Setup Wizard (Automated System Installer)
echo   [1] Start Server & Launch Web App (System Tray / No CMD Window) [Recommended]
echo   [2] Start Server & Launch Kiosk (System Tray / No CMD Window)
echo   [3] Start Server in Foreground CMD (Debug / Console Window)
echo   [4] Stop Background Server
echo   [5] Install / Verify Dependencies (Setup for New PC)
echo   [6] Open Smart Entry Kiosk (Browser)
echo   [7] Open Admin Dashboard (Browser)
echo   [8] Emergency Reset Admin Password (Console)
echo   [9] Exit
echo.
echo ===============================================================================
set /p choice="Enter your choice (0-9): "

if "%choice%"=="0" goto run_wizard
if "%choice%"=="1" goto tray_admin
if "%choice%"=="2" goto tray_kiosk
if "%choice%"=="3" goto server_only
if "%choice%"=="4" goto stop_server
if "%choice%"=="5" goto install_deps
if "%choice%"=="6" goto open_kiosk
if "%choice%"=="7" goto open_admin
if "%choice%"=="8" goto reset_pw
if "%choice%"=="9" exit /b 0

echo.
echo [!] Invalid selection! Please enter a number from 0 to 9.
timeout /t 2 >nul
goto menu

:run_wizard
echo.
echo [*] Launching SMART ENTRY Setup Wizard...
if exist "%PROJECT_ROOT%\Smart_Entry_Setup.exe" (
    start "" "%PROJECT_ROOT%\Smart_Entry_Setup.exe"
    exit /b 0
)
call :check_python
start "" %PYTHONW_CMD% "%PROJECT_ROOT%\setup_wizard.py"
exit /b 0

:check_python
where python >nul 2>nul
if %ERRORLEVEL% NEQ 0 (
    echo.
    echo ===============================================================================
    echo [ERROR] Python is not installed or not found in your system PATH!
    echo ===============================================================================
    echo 1. Download Python 3.10+ from https://www.python.org/downloads/
    echo 2. During installation, BE SURE to check: [X] "Add Python to PATH"
    echo 3. Restart this launcher after installing Python.
    echo ===============================================================================
    echo.
    pause
    goto menu
)
goto :eof

:check_deps_auto
"%PYTHON_CMD%" -c "import flask, cv2, numpy, flask_login, flask_bcrypt, PIL" >nul 2>nul
if %ERRORLEVEL% NEQ 0 (
    echo [*] Checking and installing missing dependencies...
    "%PYTHON_CMD%" -m pip install -r requirements.txt
)
goto :eof

:install_deps
cls
echo ===============================================================================
echo            INSTALLING / VERIFYING DEPENDENCIES FOR NEW PC
echo ===============================================================================
echo.
call :check_python

echo [*] Upgrading pip package installer...
"%PYTHON_CMD%" -m pip install --upgrade pip

echo.
echo [*] Installing required packages from requirements.txt...
"%PYTHON_CMD%" -m pip install -r requirements.txt

echo.
echo [*] Verifying critical modules...
"%PYTHON_CMD%" -c "import flask, flask_login, flask_bcrypt, cv2, numpy, PIL; print('  [OK] Core modules verified successfully!')"

echo.
echo ===============================================================================
echo [SUCCESS] Dependencies installed and verified! Ready to run SMART ENTRY.
echo ===============================================================================
echo.
pause
goto menu

:tray_admin
call :check_python
call :check_deps_auto
if exist "%PROJECT_ROOT%\tray_app.py" (
    start "" "%PYTHONW_CMD%" tray_app.py --admin
    exit /b 0
)
goto direct_admin

:tray_kiosk
call :check_python
call :check_deps_auto
if exist "%PROJECT_ROOT%\tray_app.py" (
    start "" "%PYTHONW_CMD%" tray_app.py --kiosk
    exit /b 0
)
goto direct_kiosk

:direct_tray
call :check_python
call :check_deps_auto
if exist "%PROJECT_ROOT%\tray_app.py" (
    start "" "%PYTHONW_CMD%" tray_app.py
    exit /b 0
)
goto server_only

:direct_kiosk
call :check_python
netstat -ano | findstr :5000 | findstr LISTENING >nul
if %ERRORLEVEL% EQU 0 (
    start http://localhost:5000/kiosk
    exit /b 0
)
call :check_deps_auto
if exist "%PROJECT_ROOT%\tray_app.py" (
    start "" "%PYTHONW_CMD%" tray_app.py --kiosk
    exit /b 0
)
start "SMART ENTRY Server - CSU Athenaeum" /d "%PROJECT_ROOT%" cmd /k "%PYTHON_CMD% app.py"
timeout /t 2 >nul
start http://localhost:5000/kiosk
exit /b 0

:direct_admin
call :check_python
netstat -ano | findstr :5000 | findstr LISTENING >nul
if %ERRORLEVEL% EQU 0 (
    start http://localhost:5000/admin
    exit /b 0
)
call :check_deps_auto
if exist "%PROJECT_ROOT%\tray_app.py" (
    start "" "%PYTHONW_CMD%" tray_app.py --admin
    exit /b 0
)
start "SMART ENTRY Server - CSU Athenaeum" /d "%PROJECT_ROOT%" cmd /k "%PYTHON_CMD% app.py"
timeout /t 2 >nul
start http://localhost:5000/admin
exit /b 0

:stop_server
cls
echo ===============================================================================
echo                 STOPPING SMART ENTRY BACKGROUND SERVER
echo ===============================================================================
echo.
for /f "tokens=5" %%a in ('netstat -ano ^| findstr :5000 ^| findstr LISTENING') do (
    taskkill /f /pid %%a >nul 2>nul
    echo [OK] Stopped process with PID %%a
)
echo.
echo [OK] Server stopped.
timeout /t 2 >nul
goto menu

:server_only
call :check_python
echo Starting SMART ENTRY Server in a separate window...
start "SMART ENTRY Server - CSU Athenaeum" /d "%PROJECT_ROOT%" cmd /k "%PYTHON_CMD% app.py"
timeout /t 2 >nul
goto menu

:open_kiosk
start http://localhost:5000/kiosk
goto menu

:open_admin
start http://localhost:5000/admin
goto menu

:reset_pw
cls
call :check_python
"%PYTHON_CMD%" reset_admin.py
echo.
pause
goto menu
