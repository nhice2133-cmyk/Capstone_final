@echo off
setlocal enabledelayedexpansion
title SMART ENTRY - Granular Backup & Disaster Recovery Tool
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
echo   SMART ENTRY: Granular Backup ^& Disaster Recovery Tool
echo ===============================================================================
echo.
echo   [1] Create System Logs ^& Alerts Backup (.zip)
echo   [2] Create Enrolled Students ^& Face Biometrics Backup (.zip)
echo   [3] Create Full System Disaster Recovery Backup (.zip)
echo   [4] Restore from a Backup Archive (Auto-detects System or Biometrics)
echo   [5] List All Available Local Backups
echo   [6] Open Backups Folder in Windows Explorer
echo   [7] Decrypt Biometric ^& Snapshot Files (.enc -^> .jpg) [Decryption Tool]
echo   [8] Exit
echo.
echo ===============================================================================
set /p "CHOICE=Enter choice [1-8]: "

if "%CHOICE%"=="1" goto CREATE_SYSTEM_BACKUP
if "%CHOICE%"=="2" goto CREATE_BIOMETRICS_BACKUP
if "%CHOICE%"=="3" goto CREATE_FULL_BACKUP
if "%CHOICE%"=="4" goto RESTORE_BACKUP
if "%CHOICE%"=="5" goto LIST_BACKUPS
if "%CHOICE%"=="6" goto OPEN_FOLDER
if "%CHOICE%"=="7" goto DECRYPT_TOOL
if "%CHOICE%"=="8" goto EXIT_TOOL
goto MENU

:CREATE_SYSTEM_BACKUP
cls
echo ===============================================================================
echo   CREATING SYSTEM LOGS ^& ALERTS BACKUP
echo ===============================================================================
echo.
echo   Capturing:
echo   - Attendance logs (time-in / time-out)
echo   - Security alerts and surveillance snapshots
echo   - Administrator credentials and recovery keys
echo   - Enrolled students and facial photos are NOT included (remains untouched)
echo.
"%PYTHON_CMD%" -c "
from tools.backup_restore import create_system_backup
path = create_system_backup(description='Offline Tool System Logs Backup', backup_type='system')
print('\n[SUCCESS] System Backup created at:\n' + path)
"
echo.
pause
goto MENU

:CREATE_BIOMETRICS_BACKUP
cls
echo ===============================================================================
echo   CREATING ENROLLED STUDENTS ^& FACE BIOMETRICS BACKUP
echo ===============================================================================
echo.
echo   Capturing:
echo   - Enrolled student profiles (names, IDs, programs)
echo   - Face crops in face_data/ (20 samples per student)
echo   - SFace deep feature embeddings and model metadata
echo   - Library attendance logs are NOT included (remains untouched)
echo.
"%PYTHON_CMD%" -c "
from tools.backup_restore import create_system_backup
path = create_system_backup(description='Offline Tool Biometrics Backup', backup_type='biometrics')
print('\n[SUCCESS] Biometrics Backup created at:\n' + path)
"
echo.
pause
goto MENU

:CREATE_FULL_BACKUP
cls
echo ===============================================================================
echo   CREATING COMPLETE SYSTEM DISASTER RECOVERY BACKUP
echo ===============================================================================
echo.
echo   Capturing:
echo   - SQLite Database (smart_entry.db) via live backup API
echo   - Enrolled student facial crops (face_data/)
echo   - SFace deep biometric embeddings ^& models
echo   - Stranger security alert snapshots
echo.
"%PYTHON_CMD%" -c "
from tools.backup_restore import create_system_backup
path = create_system_backup(description='Offline Tool Full System Backup', backup_type='full')
print('\n[SUCCESS] Full System Backup created at:\n' + path)
"
echo.
pause
goto MENU

:RESTORE_BACKUP
cls
echo ===============================================================================
echo   RESTORE FROM BACKUP ARCHIVE
echo ===============================================================================
echo.
echo   The restore engine automatically detects whether your backup archive is:
echo   - System Logs: Restores logs/alerts only (students remain untouched)
echo   - Students Biometrics: Restores students/faces only (logs remain untouched)
echo   - Full System: Restores the complete system state
echo.
"%PYTHON_CMD%" -c "
from tools.backup_restore import list_backups
backups = list_backups()
if not backups:
    print('No local backups found in backups/ directory.')
else:
    print('Available Local Backups:')
    for i, b in enumerate(backups, 1):
        print(f'  [{i}] [{b[\"type_label\"]}] {b[\"filename\"]} ({b[\"size\"]}) - {b[\"created\"]}')
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
echo   AVAILABLE LOCAL BACKUP ARCHIVES
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
        safety_tag = ' [AUTO SAFETY]' if b['is_safety'] else ''
        print(f\"* [{b['type_label']}] {b['filename']}{safety_tag}\")
        print(f\"  - Created:  {b['created']}\")
        print(f\"  - Size:     {b['size']}\")
        if b['backup_type'] == 'biometrics':
            print(f\"  - Data:     {b['total_students']} Students, {b['total_enrolled_faces']} Face Images\")
        elif b['backup_type'] == 'system':
            print(f\"  - Data:     {b['total_attendance_logs']} Attendance Logs, {b['total_security_alerts']} Alerts\")
        else:
            print(f\"  - Data:     {b['total_students']} Students, {b['total_attendance_logs']} Logs, {b['total_security_alerts']} Alerts\")
        print(f\"  - Note:     {b['description']}\")
        print()
"
echo.
pause
goto MENU

:OPEN_FOLDER
explorer "%PROJECT_ROOT%\backups"
goto MENU

:DECRYPT_TOOL
cls
"%PYTHON_CMD%" "%PROJECT_ROOT%\tools\decrypt_tool.py"
goto MENU

:EXIT_TOOL
exit /b 0
