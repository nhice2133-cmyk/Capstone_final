"""
SMART ENTRY: A Face Recognition-Based Attendance and Security Surveillance Kiosk System For The CSUCC Library
System Backup and Disaster Recovery Engine
---------------------------------------------------------------------------------------------------------
Safely captures and restores the entire state of the SMART ENTRY system:
1. SQLite relational database (patrons, attendance logs, security alerts, administrators, settings)
2. Enrolled patron facial training crops (face_data/)
3. SFace 128-D deep feature embeddings, metadata, and label mappings (recognition/models/)
4. Stranger security alert snapshots (static/snapshots/)
"""

import os
import sys
import json
import shutil
import zipfile
import sqlite3
import datetime
from pathlib import Path

# Ensure root directory is on sys.path
BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from config import Config

BACKUPS_DIR = os.path.join(BASE_DIR, "backups")
os.makedirs(BACKUPS_DIR, exist_ok=True)


def get_system_manifest() -> dict:
    """
    Inspects live system components and returns a descriptive metadata manifest.
    """
    manifest = {
        "system_title": "SMART ENTRY: A Face Recognition-Based Attendance and Security Surveillance Kiosk System For The CSUCC Library",
        "institution": "Caraga State University Cabadbaran Campus (CSUCC)",
        "facility": "Athenaeum Learning Commons Library",
        "backup_timestamp": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "version": "1.0.0",
        "total_students": 0,
        "total_attendance_logs": 0,
        "total_security_alerts": 0,
        "total_admins": 0,
        "sface_embeddings_ready": False,
        "total_enrolled_faces": 0,
        "db_size_bytes": 0,
        "included_components": [
            "database/smart_entry.db",
            "face_data/",
            "recognition/models/sface_embeddings.npz",
            "recognition/models/model_metadata.json",
            "recognition/models/label_map.json",
            "static/snapshots/"
        ]
    }

    # Query DB stats safely
    if os.path.exists(Config.DATABASE_PATH):
        try:
            manifest["db_size_bytes"] = os.path.getsize(Config.DATABASE_PATH)
            conn = sqlite3.connect(Config.DATABASE_PATH)
            c = conn.cursor()
            
            c.execute("SELECT COUNT(*) FROM students")
            manifest["total_students"] = c.fetchone()[0]

            c.execute("SELECT COUNT(*) FROM attendance_logs")
            manifest["total_attendance_logs"] = c.fetchone()[0]

            c.execute("SELECT COUNT(*) FROM security_alerts")
            manifest["total_security_alerts"] = c.fetchone()[0]

            c.execute("SELECT COUNT(*) FROM admins")
            manifest["total_admins"] = c.fetchone()[0]
            conn.close()
        except Exception as e:
            manifest["db_query_error"] = str(e)

    # Check SFace embeddings
    if os.path.exists(Config.SFACE_EMBEDDINGS_PATH):
        manifest["sface_embeddings_ready"] = True

    # Count face crops
    if os.path.exists(Config.FACE_DATA_DIR):
        total_crops = 0
        for root, dirs, files in os.walk(Config.FACE_DATA_DIR):
            if "staging" in root:
                continue
            for f in files:
                if f.lower().endswith(('.jpg', '.jpeg', '.png')):
                    total_crops += 1
        manifest["total_enrolled_faces"] = total_crops

    return manifest


def create_system_backup(output_path: str = None, description: str = "Manual System Backup") -> str:
    """
    Creates a complete, self-contained backup archive (.zip) of the SMART ENTRY system.
    Uses SQLite's online backup API to ensure zero database corruption even while the kiosk is live.
    
    Returns:
        str: Absolute path to the generated .zip backup file.
    """
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    if not output_path:
        filename = f"smart_entry_backup_{timestamp}.zip"
        output_path = os.path.join(BACKUPS_DIR, filename)

    os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)

    manifest = get_system_manifest()
    manifest["backup_description"] = description
    manifest["archive_filename"] = os.path.basename(output_path)

    # 1. Safely backup the SQLite database via sqlite3 backup API
    temp_db_copy = os.path.join(BACKUPS_DIR, f"temp_db_{timestamp}.sqlite")
    if os.path.exists(Config.DATABASE_PATH):
        src_conn = sqlite3.connect(Config.DATABASE_PATH)
        dst_conn = sqlite3.connect(temp_db_copy)
        with dst_conn:
            src_conn.backup(dst_conn, pages=100)
        dst_conn.close()
        src_conn.close()

    # 2. Package everything into the ZIP archive
    temp_zip = output_path + ".tmp"
    with zipfile.ZipFile(temp_zip, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        # Write manifest
        zf.writestr("backup_manifest.json", json.dumps(manifest, indent=2))

        # Write clean DB
        if os.path.exists(temp_db_copy):
            zf.write(temp_db_copy, arcname="database/smart_entry.db")

        # Write face_data/
        if os.path.exists(Config.FACE_DATA_DIR):
            for root, dirs, files in os.walk(Config.FACE_DATA_DIR):
                for f in files:
                    full_p = os.path.join(root, f)
                    rel_p = os.path.relpath(full_p, BASE_DIR)
                    try:
                        zf.write(full_p, arcname=rel_p.replace("\\", "/"))
                    except Exception as e:
                        print(f"[BACKUP WARN] Could not archive {rel_p}: {e}")

        # Write recognition/models/
        model_files = [
            Config.SFACE_EMBEDDINGS_PATH,
            Config.MODEL_METADATA_PATH,
            Config.LABEL_MAP_PATH
        ]
        for mf in model_files:
            if os.path.exists(mf):
                rel_p = os.path.relpath(mf, BASE_DIR)
                zf.write(mf, arcname=rel_p.replace("\\", "/"))

        # Write static/snapshots/
        if os.path.exists(Config.ALERTS_SNAPSHOT_DIR):
            for root, dirs, files in os.walk(Config.ALERTS_SNAPSHOT_DIR):
                for f in files:
                    if f.lower().endswith(('.jpg', '.jpeg', '.png')):
                        full_p = os.path.join(root, f)
                        rel_p = os.path.relpath(full_p, BASE_DIR)
                        try:
                            zf.write(full_p, arcname=rel_p.replace("\\", "/"))
                        except Exception as e:
                            print(f"[BACKUP WARN] Could not archive snapshot {rel_p}: {e}")

    # Remove temp DB copy
    if os.path.exists(temp_db_copy):
        try:
            os.remove(temp_db_copy)
        except Exception:
            pass

    # Finalize ZIP
    if os.path.exists(output_path):
        os.remove(output_path)
    os.rename(temp_zip, output_path)

    return output_path


def validate_backup_file(zip_path_or_file) -> tuple:
    """
    Validates that a given file is a legitimate SMART ENTRY backup archive.
    
    Returns:
        (is_valid: bool, error_message: str, manifest: dict)
    """
    try:
        with zipfile.ZipFile(zip_path_or_file, "r") as zf:
            namelist = zf.namelist()
            
            # Must contain at least database/smart_entry.db or backup_manifest.json
            has_db = any("database/smart_entry.db" in name.replace("\\", "/") for name in namelist)
            has_manifest = "backup_manifest.json" in namelist

            if not has_db and not has_manifest:
                return (
                    False, 
                    "Invalid archive: Missing required database or backup_manifest.json.", 
                    {}
                )

            manifest = {}
            if has_manifest:
                try:
                    manifest_raw = zf.read("backup_manifest.json").decode("utf-8")
                    manifest = json.loads(manifest_raw)
                except Exception:
                    pass

            return (True, "Valid SMART ENTRY backup archive.", manifest)
    except zipfile.BadZipFile:
        return (False, "The provided file is not a valid or readable ZIP archive.", {})
    except Exception as e:
        return (False, f"Verification error: {str(e)}", {})


def restore_system_backup(zip_path_or_file, create_safety_snapshot: bool = True) -> tuple:
    """
    Restores the SMART ENTRY system from a verified backup archive.
    
    1. Optionally creates an automatic pre-restore safety snapshot of current data.
    2. Overwrites database/smart_entry.db.
    3. Overwrites/restores face_data/ training samples.
    4. Overwrites/restores recognition/models/ embeddings and metadata.
    5. Overwrites/restores static/snapshots/ security alerts.
    6. Reloads live recognizer cache in the running web application if accessible.
    
    Returns:
        (success: bool, message: str)
    """
    is_valid, err_msg, manifest = validate_backup_file(zip_path_or_file)
    if not is_valid:
        return (False, err_msg)

    # 1. Automatic safety snapshot before destructive overwrite
    if create_safety_snapshot:
        try:
            safety_ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
            safety_path = os.path.join(BACKUPS_DIR, f"pre_restore_safety_{safety_ts}.zip")
            create_system_backup(output_path=safety_path, description="Auto-generated safety snapshot before restore")
        except Exception as e:
            print(f"[WARN] Could not create pre-restore safety snapshot: {e}")

    # 2. Extract contents
    try:
        with zipfile.ZipFile(zip_path_or_file, "r") as zf:
            for member in zf.infolist():
                filename = member.filename.replace("\\", "/")
                
                # Prevent directory traversal attacks
                if filename.startswith("/") or ".." in filename:
                    continue

                # Target extraction path
                target_path = os.path.join(BASE_DIR, filename)
                
                if member.is_dir():
                    os.makedirs(target_path, exist_ok=True)
                    continue

                os.makedirs(os.path.dirname(target_path), exist_ok=True)
                with zf.open(member) as source, open(target_path, "wb") as target:
                    shutil.copyfileobj(source, target)

        # 3. Reload in-memory recognizer if kiosk routes module is loaded
        try:
            from routes.kiosk import _reload_recognizer
            _reload_recognizer()
        except Exception as e:
            pass

        restored_students = manifest.get("total_students", "enrolled")
        restored_logs = manifest.get("total_attendance_logs", "attendance")
        return (
            True, 
            f"System successfully restored! Active state: {restored_students} patron(s), {restored_logs} attendance log(s), and deep biometrics synced."
        )
    except Exception as e:
        return (False, f"Restore failed during extraction: {str(e)}")


def list_backups() -> list:
    """
    Returns a sorted list of available local backup archives in the backups/ directory.
    """
    if not os.path.exists(BACKUPS_DIR):
        return []

    backups = []
    for f in os.listdir(BACKUPS_DIR):
        if not f.lower().endswith(".zip"):
            continue
        full_p = os.path.join(BACKUPS_DIR, f)
        if not os.path.isfile(full_p):
            continue

        stat = os.stat(full_p)
        created_time = datetime.datetime.fromtimestamp(stat.st_mtime).strftime("%Y-%m-%d %H:%M:%S")
        size_mb = round(stat.st_size / (1024 * 1024), 2)
        size_str = f"{size_mb} MB" if size_mb >= 0.1 else f"{round(stat.st_size / 1024, 1)} KB"

        # Try to read manifest
        manifest = {}
        try:
            with zipfile.ZipFile(full_p, "r") as zf:
                if "backup_manifest.json" in zf.namelist():
                    manifest = json.loads(zf.read("backup_manifest.json").decode("utf-8"))
        except Exception:
            pass

        backups.append({
            "filename": f,
            "path": full_p,
            "size": size_str,
            "created": created_time,
            "timestamp_sort": stat.st_mtime,
            "is_safety": f.startswith("pre_restore_safety"),
            "description": manifest.get("backup_description", "System Backup Archive"),
            "total_students": manifest.get("total_students", 0),
            "total_attendance_logs": manifest.get("total_attendance_logs", 0),
            "total_security_alerts": manifest.get("total_security_alerts", 0),
            "has_embeddings": manifest.get("sface_embeddings_ready", False)
        })

    # Sort descending by timestamp
    backups.sort(key=lambda x: x["timestamp_sort"], reverse=True)
    return backups


def delete_backup(filename: str) -> bool:
    """
    Safely deletes a backup archive from backups/.
    """
    safe_name = os.path.basename(filename)
    target = os.path.join(BACKUPS_DIR, safe_name)
    if os.path.exists(target) and os.path.isfile(target):
        try:
            os.remove(target)
            return True
        except Exception:
            return False
    return False


if __name__ == "__main__":
    print("=" * 70)
    print(" SMART ENTRY: System Backup & Disaster Recovery Engine")
    print("=" * 70)
    manifest = get_system_manifest()
    print(f"System Title:   {manifest['system_title']}")
    print(f"Facility:       {manifest['facility']}")
    print(f"Patrons:        {manifest['total_students']}")
    print(f"Attendance:     {manifest['total_attendance_logs']}")
    print(f"Alerts:         {manifest['total_security_alerts']}")
    print(f"Embeddings:     {'Active' if manifest['sface_embeddings_ready'] else 'None'}")
    print("-" * 70)
    print("Creating test backup...")
    path = create_system_backup()
    print(f"[SUCCESS] Backup created at: {path}")
    print(f"Available backups: {len(list_backups())}")

