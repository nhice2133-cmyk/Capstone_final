@echo off
setlocal enabledelayedexpansion
title SMART ENTRY - System Backup & Disaster Recovery
color 0A

:: Resolve absolute project directory
set "PROJECT_ROOT=%~dp0"
if "%PROJECT_ROOT:~-1%"=="\" set "PROJECT_ROOT=%PROJECT_ROOT:~0,-1%"
cd /d "%PROJECT_ROOT%"

:: Determine Python executable
if exist "%PROJECT_ROOT%\venv\Scripts\python.exe" (
    set "PYTHON_CMD=%PROJECT_ROOT%\venv\Scripts\python.exe"
) else (
    set "PYTHON_CMD=python"
)

:MENU
cls
echo ===============================================================================
echo   CARAGA STATE UNIVERSITY CABADBARAN CAMPUS (CSUCC) - ATHENAEUM LIBRARY
echo   SMART ENTRY: System Backup & Disaster Recovery Tool
echo ===============================================================================
echo.
echo   [1] Create Full System Backup (.zip)
echo   [2] Restore System from a Backup Archive (.zip)
echo   [3] List All Available Local Backups
echo   [4] Open Backups Folder in Windows Explorer
echo   [5] Launch SMART ENTRY Web Application
echo   [6] Exit
echo.
echo ===============================================================================
set /p "CHOICE=Enter choice [1-6]: "

if "%CHOICE%"=="1" goto CREATE_BACKUP
if "%CHOICE%"=="2" goto RESTORE_BACKUP
if "%CHOICE%"=="3" goto LIST_BACKUPS
if "%CHOICE%"=="4" goto OPEN_FOLDER
if "%CHOICE%"=="5" goto LAUNCH_APP
if "%CHOICE%"=="6" goto EXIT_TOOL
goto MENU

:CREATE_BACKUP
cls
echo ===============================================================================
echo   CREATING COMPLETE SYSTEM BACKUP
echo ===============================================================================
echo.
echo   Capturing:
echo   - SQLite Database (smart_entry.db) via live backup API
echo   - Enrolled Student Face Crops (face_data/)
echo   - SFace Deep Biometric Embeddings & Model Metadata (recognition/models/)
echo   - Stranger Security Alert Snapshots (static/snapshots/)
echo.
"%PYTHON_CMD%" -c "
import sys
from tools.backup_restore import create_system_backup
path = create_system_backup(description='Offline Windows Tool Backup')
print('\n[SUCCESS] Backup created at: ' + path)
"
echo.
set /p "COPY_DESK=Copy this backup to your Desktop for safe keeping? (Y/N): "
if /i "%COPY_DESK%"=="Y" (
    "%PYTHON_CMD%" -c "
import os, shutil
from tools.backup_restore import list_backups
backups = list_backups()
if backups:
    src = backups[0]['path']
    desktop = os.path.join(os.environ['USERPROFILE'], 'Desktop')
    dst = os.path.join(desktop, backups[0]['filename'])
    shutil.copy2(src, dst)
    print('[SUCCESS] Copied to Desktop: ' + dst)
"
)
echo.
pause
goto MENU

:RESTORE_BACKUP
cls
echo ===============================================================================
echo   RESTORE SYSTEM FROM BACKUP ARCHIVE
echo ===============================================================================
echo.
echo   WARNING: Restoring will overwrite existing patron profiles, attendance
echo   logs, and SFace deep facial embeddings with the backup contents.
echo   (An automatic pre-restore safety snapshot will be created before proceeding)
echo.
"%PYTHON_CMD%" -c "
from tools.backup_restore import list_backups
backups = list_backups()
if not backups:
    print('No local backups found in backups/ directory.')
else:
    print('Available Local Backups:')
    for i, b in enumerate(backups, 1):
        print(f'  [{i}] {b[\"filename\"]} ({b[\"size\"]}) - {b[\"created\"]}')
"
echo.
echo   Enter the backup number from above, or drag and drop a .zip file here:
set /p "TARGET_INPUT=Selection or File Path: "

if "%TARGET_INPUT%"=="" (
    echo [ABORTED] No selection made.
    pause
    goto MENU
)

"%PYTHON_CMD%" -c "
import sys, os
from tools.backup_restore import restore_system_backup, list_backups

target = '''%TARGET_INPUT%'''.strip('\"\'')
backups = list_backups()

restore_path = None
if target.isdigit():
    idx = int(target) - 1
    if 0 <= idx < len(backups):
        restore_path = backups[idx]['path']
elif os.path.exists(target):
    restore_path = target

if not restore_path:
    print(f'[ERROR] Target file not found: {target}')
    sys.exit(1)

print(f'\nRestoring from: {restore_path}...')
success, msg = restore_system_backup(restore_path, create_safety_snapshot=True)
if success:
    print('\n[SUCCESS] ' + msg)
else:
    print('\n[ERROR] ' + msg)
"
echo.
pause
goto MENU

:LIST_BACKUPS
cls
echo ===============================================================================
echo   AVAILABLE LOCAL SYSTEM BACKUPS
echo ===============================================================================
echo.
"%PYTHON_CMD%" -c "
from tools.backup_restore import list_backups
backups = list_backups()
if not backups:
    print('No backup archives found.')
else:
    print(f'Total Snapshots: {len(backups)}\n')
    for b in backups:
        safety_tag = ' [AUTO SAFETY SNAPSHOT]' if b['is_safety'] else ''
        print(f\"* {b['filename']}{safety_tag}\")
        print(f\"  - Created:  {b['created']}\")
        print(f\"  - Size:     {b['size']}\")
        print(f\"  - Data:     {b['total_students']} Patrons, {b['total_attendance_logs']} Logs, {b['total_security_alerts']} Alerts\")
        print(f\"  - SFace:    {'128-D Embeddings Active' if b['has_embeddings'] else 'None'}\")
        print(f\"  - Note:     {b['description']}\")
        print()
"
echo.
pause
goto MENU

:OPEN_FOLDER
explorer "%PROJECT_ROOT%\backups"
goto MENU

:LAUNCH_APP
start "" "%PROJECT_ROOT%\smart_entry_launcher.bat"
goto MENU

:EXIT_TOOL
exit /b 0

