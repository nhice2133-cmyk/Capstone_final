"""
SMART ENTRY: A Face Recognition-Based Attendance and Security Surveillance Kiosk System For The CSUCC Library
System Backup and Disaster Recovery Engine
---------------------------------------------------------------------------------------------------------
Provides granular, independent backup and restore capabilities:
1. System Core & Logs (Attendance logs, security alerts, alert snapshots, admin credentials, settings)
2. Enrolled Students & Face Biometrics (Student profiles, 20 facial samples in face_data/, SFace embeddings)
3. Full System Archive (Combined complete disaster recovery)
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
            conn.row_factory = sqlite3.Row
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
                if f.lower().endswith(('.jpg', '.jpeg', '.png', '.enc')):
                    total_crops += 1
        manifest["total_enrolled_faces"] = total_crops

    return manifest


def _dump_table_records(conn, table_name: str) -> list:
    """Helper to dump table rows as a list of dictionaries."""
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    c.execute(f"SELECT * FROM {table_name}")
    return [dict(row) for row in c.fetchall()]


def create_system_backup(output_path: str = None, description: str = None, backup_type: str = "system") -> str:
    """
    Creates an independent backup archive (.zip) based on backup_type:
    - 'system': Attendance logs, security alerts, alert snapshots, admin accounts, and settings.
    - 'biometrics': Enrolled student records, face_data/ image crops, and SFace model embeddings.
    - 'full': Complete system snapshot combining both system data and biometrics.

    Returns:
        str: Absolute path to the generated .zip backup file.
    """
    backup_type = (backup_type or "system").lower().strip()
    if backup_type not in ["system", "biometrics", "full"]:
        backup_type = "system"

    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    if not output_path:
        if backup_type == "biometrics":
            prefix = "smart_entry_biometrics"
            default_desc = "Enrolled Students & Biometrics Archive"
        elif backup_type == "system":
            prefix = "smart_entry_system"
            default_desc = "System Core & Logs Archive"
        else:
            prefix = "smart_entry_full"
            default_desc = "Full System Disaster Recovery Archive"

        filename = f"{prefix}_backup_{timestamp}.zip"
        output_path = os.path.join(BACKUPS_DIR, filename)
    else:
        default_desc = f"{backup_type.capitalize()} Archive"

    if not description:
        description = default_desc

    os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)

    manifest = get_system_manifest()
    manifest["backup_type"] = backup_type
    manifest["backup_description"] = description
    manifest["archive_filename"] = os.path.basename(output_path)
    manifest["created_at"] = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    # Connect to live SQLite database
    conn = sqlite3.connect(Config.DATABASE_PATH)
    conn.row_factory = sqlite3.Row

    temp_zip = output_path + ".tmp"
    with zipfile.ZipFile(temp_zip, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        
        # ── 1. BIOMETRICS BACKUP (Students & Face Images) ───────────────────
        if backup_type in ["biometrics", "full"]:
            # Dump students table
            students_data = _dump_table_records(conn, "students")
            zf.writestr("database/students_data.json", json.dumps(students_data, indent=2))
            manifest["total_students"] = len(students_data)

            # Archive face_data/
            enrolled_crops_count = 0
            if os.path.exists(Config.FACE_DATA_DIR):
                for root, dirs, files in os.walk(Config.FACE_DATA_DIR):
                    if "staging" in root:
                        continue
                    for f in files:
                        full_p = os.path.join(root, f)
                        rel_p = os.path.relpath(full_p, BASE_DIR)
                        try:
                            zf.write(full_p, arcname=rel_p.replace("\\", "/"))
                            if f.lower().endswith(('.enc', '.jpg', '.jpeg', '.png')):
                                enrolled_crops_count += 1
                        except Exception as e:
                            print(f"[BACKUP WARN] Could not archive face file {rel_p}: {e}")
            manifest["total_enrolled_faces"] = enrolled_crops_count

            # Archive recognition/models/
            model_files = [
                Config.SFACE_EMBEDDINGS_PATH,
                Config.MODEL_METADATA_PATH,
                Config.LABEL_MAP_PATH
            ]
            for mf in model_files:
                if os.path.exists(mf):
                    rel_p = os.path.relpath(mf, BASE_DIR)
                    zf.write(mf, arcname=rel_p.replace("\\", "/"))

        # ── 2. SYSTEM DATA BACKUP (Logs, Alerts, Admins, Snapshots) ─────────
        if backup_type in ["system", "full"]:
            system_data = {
                "attendance_logs": _dump_table_records(conn, "attendance_logs"),
                "security_alerts": _dump_table_records(conn, "security_alerts"),
                "admins": _dump_table_records(conn, "admins"),
            }
            zf.writestr("database/system_data.json", json.dumps(system_data, indent=2))
            manifest["total_attendance_logs"] = len(system_data["attendance_logs"])
            manifest["total_security_alerts"] = len(system_data["security_alerts"])
            manifest["total_admins"] = len(system_data["admins"])

            # Archive static/snapshots/
            if os.path.exists(Config.ALERTS_SNAPSHOT_DIR):
                for root, dirs, files in os.walk(Config.ALERTS_SNAPSHOT_DIR):
                    for f in files:
                        if f.lower().endswith(('.jpg', '.jpeg', '.png', '.enc')):
                            full_p = os.path.join(root, f)
                            rel_p = os.path.relpath(full_p, BASE_DIR)
                            try:
                                zf.write(full_p, arcname=rel_p.replace("\\", "/"))
                            except Exception as e:
                                print(f"[BACKUP WARN] Could not archive snapshot {rel_p}: {e}")

        # ── 3. FULL BACKUP EXTRAS ───────────────────────────────────────────
        if backup_type == "full":
            temp_db_copy = os.path.join(BACKUPS_DIR, f"temp_db_{timestamp}.sqlite")
            try:
                dst_conn = sqlite3.connect(temp_db_copy)
                with dst_conn:
                    conn.backup(dst_conn, pages=100)
                dst_conn.close()
                if os.path.exists(temp_db_copy):
                    zf.write(temp_db_copy, arcname="database/smart_entry.db")
                    os.remove(temp_db_copy)
            except Exception as e:
                print(f"[BACKUP WARN] Could not package raw database file: {e}")

        # Write manifest
        zf.writestr("backup_manifest.json", json.dumps(manifest, indent=2))

    conn.close()

    # Finalize ZIP
    if os.path.exists(output_path):
        try:
            os.remove(output_path)
        except Exception:
            pass
    os.rename(temp_zip, output_path)

    return output_path


def validate_backup_file(zip_path_or_file) -> tuple:
    """
    Validates that a given file is a legitimate SMART ENTRY backup archive and detects its type.
    
    Returns:
        (is_valid: bool, error_message: str, manifest: dict, detected_type: str)
    """
    try:
        with zipfile.ZipFile(zip_path_or_file, "r") as zf:
            namelist = [n.replace("\\", "/") for n in zf.namelist()]
            
            has_db = "database/smart_entry.db" in namelist
            has_system = "database/system_data.json" in namelist
            has_students = "database/students_data.json" in namelist
            has_manifest = "backup_manifest.json" in namelist

            if not (has_db or has_system or has_students or has_manifest):
                return (
                    False, 
                    "Invalid archive: Missing required database or manifest.", 
                    {},
                    "unknown"
                )

            manifest = {}
            if has_manifest:
                try:
                    manifest_raw = zf.read("backup_manifest.json").decode("utf-8")
                    manifest = json.loads(manifest_raw)
                except Exception:
                    pass

            # Detect type
            detected_type = manifest.get("backup_type")
            if not detected_type:
                if has_students and not has_system and not has_db:
                    detected_type = "biometrics"
                elif has_system and not has_students and not has_db:
                    detected_type = "system"
                else:
                    detected_type = "full"

            return (True, "Valid SMART ENTRY backup archive.", manifest, detected_type)
    except zipfile.BadZipFile:
        return (False, "The provided file is not a valid or readable ZIP archive.", {}, "unknown")
    except Exception as e:
        return (False, f"Verification error: {str(e)}", {}, "unknown")


def restore_system_backup(zip_path_or_file, create_safety_snapshot: bool = True, force_type: str = None) -> tuple:
    """
    Selectively and safely restores from a backup archive:
    - If backup_type is 'system':
        Restores attendance logs, security alerts, and snapshots.
        PRESERVES existing enrolled students and face images untouched!
    - If backup_type is 'biometrics':
        Restores enrolled students, face_data/ image crops, and models.
        PRESERVES existing attendance logs, alerts, and admin accounts untouched!
    - If backup_type is 'full' (or legacy):
        Restores complete system state.
        
    Returns:
        (success: bool, message: str)
    """
    is_valid, err_msg, manifest, detected_type = validate_backup_file(zip_path_or_file)
    if not is_valid:
        return (False, err_msg)

    restore_type = (force_type or detected_type or "full").lower()

    # 1. Automatic safety snapshot before destructive changes
    if create_safety_snapshot:
        try:
            safety_ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
            safety_path = os.path.join(BACKUPS_DIR, f"pre_restore_{restore_type}_safety_{safety_ts}.zip")
            create_system_backup(output_path=safety_path, description=f"Safety snapshot before restoring {restore_type}", backup_type=restore_type)
        except Exception as e:
            print(f"[WARN] Could not create pre-restore safety snapshot: {e}")

    try:
        with zipfile.ZipFile(zip_path_or_file, "r") as zf:
            namelist = [m.filename.replace("\\", "/") for m in zf.infolist()]

            conn = sqlite3.connect(Config.DATABASE_PATH)
            conn.execute("PRAGMA foreign_keys = OFF;")

            # ── A. RESTORE BIOMETRICS (Students & Face Images) ──────────────
            if restore_type in ["biometrics", "full"]:
                # 1. Restore face_data/ files
                for member in zf.infolist():
                    fname = member.filename.replace("\\", "/")
                    if fname.startswith("/") or ".." in fname:
                        continue
                    if fname.startswith("face_data/") or fname.startswith("recognition/models/"):
                        target_p = os.path.join(BASE_DIR, fname)
                        if member.is_dir():
                            os.makedirs(target_p, exist_ok=True)
                        else:
                            os.makedirs(os.path.dirname(target_p), exist_ok=True)
                            with zf.open(member) as src, open(target_p, "wb") as dst:
                                shutil.copyfileobj(src, dst)

                # 2. Restore students table in SQLite
                if "database/students_data.json" in namelist:
                    students_json = zf.read("database/students_data.json").decode("utf-8")
                    students_list = json.loads(students_json)
                    with conn:
                        conn.execute("DELETE FROM students;")
                        for s in students_list:
                            conn.execute("""
                                INSERT INTO students (id, full_name, student_id, program, status, enrolled_at)
                                VALUES (?, ?, ?, ?, ?, ?)
                            """, (
                                s.get("id"),
                                s.get("full_name"),
                                s.get("student_id"),
                                s.get("program", "BSIT"),
                                s.get("status", "active"),
                                s.get("enrolled_at", datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
                            ))

            # ── B. RESTORE SYSTEM DATA (Logs, Alerts, Admins, Snapshots) ────
            if restore_type in ["system", "full"]:
                # 1. Restore static/snapshots/ files
                for member in zf.infolist():
                    fname = member.filename.replace("\\", "/")
                    if fname.startswith("/") or ".." in fname:
                        continue
                    if fname.startswith("static/snapshots/"):
                        target_p = os.path.join(BASE_DIR, fname)
                        if member.is_dir():
                            os.makedirs(target_p, exist_ok=True)
                        else:
                            os.makedirs(os.path.dirname(target_p), exist_ok=True)
                            with zf.open(member) as src, open(target_p, "wb") as dst:
                                shutil.copyfileobj(src, dst)

                # 2. Restore system tables in SQLite
                if "database/system_data.json" in namelist:
                    sys_json = zf.read("database/system_data.json").decode("utf-8")
                    sys_data = json.loads(sys_json)
                    with conn:
                        # Restore attendance logs
                        conn.execute("DELETE FROM attendance_logs;")
                        for log in sys_data.get("attendance_logs", []):
                            conn.execute("""
                                INSERT INTO attendance_logs (id, student_db_id, date, time_in, time_out, visit_purpose, node)
                                VALUES (?, ?, ?, ?, ?, ?, ?)
                            """, (
                                log.get("id"),
                                log.get("student_db_id"),
                                log.get("date"),
                                log.get("time_in"),
                                log.get("time_out"),
                                log.get("visit_purpose"),
                                log.get("node", "entry")
                            ))

                        # Restore security alerts
                        conn.execute("DELETE FROM security_alerts;")
                        for alert in sys_data.get("security_alerts", []):
                            conn.execute("""
                                INSERT INTO security_alerts (id, detected_at, snapshot_path, confidence_score, resolved)
                                VALUES (?, ?, ?, ?, ?)
                            """, (
                                alert.get("id"),
                                alert.get("detected_at"),
                                alert.get("snapshot_path"),
                                alert.get("confidence_score"),
                                alert.get("resolved", 0)
                            ))

                        # Restore admins (if present)
                        admins_list = sys_data.get("admins", [])
                        if admins_list:
                            conn.execute("DELETE FROM admins;")
                            for adm in admins_list:
                                conn.execute("""
                                    INSERT INTO admins (id, username, password_hash, created_at, security_question, security_answer_hash, recovery_key_hash)
                                    VALUES (?, ?, ?, ?, ?, ?, ?)
                                """, (
                                    adm.get("id"),
                                    adm.get("username"),
                                    adm.get("password_hash"),
                                    adm.get("created_at"),
                                    adm.get("security_question"),
                                    adm.get("security_answer_hash"),
                                    adm.get("recovery_key_hash")
                                ))

            # ── C. LEGACY FULL RESTORE FALLBACK ─────────────────────────────
            if restore_type == "full" and "database/smart_entry.db" in namelist and "database/system_data.json" not in namelist:
                # Legacy full database archive extraction
                conn.close()
                target_db = Config.DATABASE_PATH
                with zf.open("database/smart_entry.db") as src, open(target_db, "wb") as dst:
                    shutil.copyfileobj(src, dst)
                conn = sqlite3.connect(Config.DATABASE_PATH)

            conn.execute("PRAGMA foreign_keys = ON;")
            conn.close()

        # Reload live model recognizer in application memory
        try:
            from routes.kiosk import _reload_recognizer
            _reload_recognizer()
        except Exception:
            pass

        if restore_type == "biometrics":
            return (
                True,
                f"Enrolled students and face images successfully restored ({manifest.get('total_students', 0)} students, {manifest.get('total_enrolled_faces', 0)} face crops). System attendance logs and settings were preserved."
            )
        elif restore_type == "system":
            return (
                True,
                f"System attendance logs and alerts successfully restored ({manifest.get('total_attendance_logs', 0)} logs, {manifest.get('total_security_alerts', 0)} alerts). Enrolled students and biometrics were preserved."
            )
        else:
            return (
                True,
                f"Full system state successfully restored ({manifest.get('total_students', 0)} students, {manifest.get('total_attendance_logs', 0)} logs, {manifest.get('total_security_alerts', 0)} alerts)."
            )

    except Exception as e:
        return (False, f"Restore failed during extraction: {str(e)}")


def list_backups() -> list:
    """
    Returns a sorted list of available local backup archives categorized by type.
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

        manifest = {}
        backup_type = "full"
        try:
            with zipfile.ZipFile(full_p, "r") as zf:
                namelist = [n.replace("\\", "/") for n in zf.namelist()]
                if "backup_manifest.json" in namelist:
                    manifest = json.loads(zf.read("backup_manifest.json").decode("utf-8"))
                    backup_type = manifest.get("backup_type") or "full"
                else:
                    if "database/students_data.json" in namelist and "database/system_data.json" not in namelist:
                        backup_type = "biometrics"
                    elif "database/system_data.json" in namelist and "database/students_data.json" not in namelist:
                        backup_type = "system"
                    else:
                        backup_type = "full"
        except Exception:
            pass

        # Friendly type labels and badges
        if backup_type == "biometrics":
            type_label = "Students & Biometrics"
            badge_class = "badge-csucc"
            type_icon = "👥"
        elif backup_type == "system":
            type_label = "System Logs & Alerts"
            badge_class = "badge-primary"
            type_icon = "📋"
        else:
            type_label = "Full System Archive"
            badge_class = "badge-gold"
            type_icon = "📦"

        backups.append({
            "filename": f,
            "path": full_p,
            "size": size_str,
            "created": created_time,
            "timestamp_sort": stat.st_mtime,
            "is_safety": f.startswith("pre_restore_"),
            "backup_type": backup_type,
            "type_label": type_label,
            "type_icon": type_icon,
            "badge_class": badge_class,
            "description": manifest.get("backup_description", f"{type_label} Backup"),
            "total_students": manifest.get("total_students", 0),
            "total_enrolled_faces": manifest.get("total_enrolled_faces", 0),
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
    print(f"Enrolled Crops: {manifest['total_enrolled_faces']}")
    print(f"Attendance:     {manifest['total_attendance_logs']}")
    print(f"Alerts:         {manifest['total_security_alerts']}")
    print(f"Embeddings:     {'Active' if manifest['sface_embeddings_ready'] else 'None'}")
    print("-" * 70)
    print("Testing separated backups...")
    sys_path = create_system_backup(backup_type="system", description="Test System Logs Backup")
    print(f"[SUCCESS] System backup: {sys_path}")
    bio_path = create_system_backup(backup_type="biometrics", description="Test Biometrics Backup")
    print(f"[SUCCESS] Biometrics backup: {bio_path}")
    print(f"Available backups: {len(list_backups())}")
