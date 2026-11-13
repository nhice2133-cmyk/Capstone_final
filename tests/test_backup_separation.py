"""
Unit & Integration Test for Separated System vs Biometrics Backup & Restore
"""
import os
import sys
import sqlite3

# Ensure root is on path
BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from config import Config
from tools.backup_restore import create_system_backup, restore_system_backup, list_backups

def run_test():
    print("=" * 60)
    print("TESTING SEPARATED BACKUP & RESTORE ARCHITECTURE")
    print("=" * 60)

    # 1. Setup known test records
    conn = sqlite3.connect(Config.DATABASE_PATH)
    conn.execute("INSERT OR REPLACE INTO students (id, full_name, student_id, program) VALUES (999, 'Original Student', 'STU-999', 'BSIT')")
    conn.execute("INSERT OR REPLACE INTO attendance_logs (id, student_db_id, date, time_in, node) VALUES (999, 999, '2026-11-13', '08:00:00', 'entry')")
    conn.commit()
    conn.close()

    # 2. Create Biometrics backup (captures student 999)
    bio_zip = create_system_backup(backup_type="biometrics", description="Test Biometric Snapshot")
    assert os.path.exists(bio_zip)
    print("  [PASS] Biometrics backup created:", os.path.basename(bio_zip))

    # 3. Create System backup (captures attendance log 999)
    sys_zip = create_system_backup(backup_type="system", description="Test System Snapshot")
    assert os.path.exists(sys_zip)
    print("  [PASS] System backup created:", os.path.basename(sys_zip))

    # 4. Modify state: change student name and add an attendance log 1000
    conn = sqlite3.connect(Config.DATABASE_PATH)
    conn.execute("UPDATE students SET full_name = 'Modified Student' WHERE id = 999")
    conn.execute("INSERT OR REPLACE INTO attendance_logs (id, student_db_id, date, time_in, node) VALUES (1000, 999, '2026-11-13', '09:00:00', 'entry')")
    conn.commit()
    conn.close()

    # 5. Restore Biometrics backup:
    # Must restore student 999 back to 'Original Student'
    # BUT MUST KEEP new attendance log 1000 intact!
    ok, msg = restore_system_backup(bio_zip, create_safety_snapshot=False)
    assert ok, f"Biometrics restore failed: {msg}"
    print("  [PASS] Biometrics restore completed:", msg)

    conn = sqlite3.connect(Config.DATABASE_PATH)
    s_name = conn.execute("SELECT full_name FROM students WHERE id = 999").fetchone()[0]
    assert s_name == "Original Student", f"Expected 'Original Student', got '{s_name}'"
    print("  [PASS] Enrolled student profile correctly restored.")

    log_count = conn.execute("SELECT COUNT(*) FROM attendance_logs WHERE id = 1000").fetchone()[0]
    assert log_count == 1, "Attendance log 1000 was improperly modified during biometrics restore!"
    print("  [PASS] System attendance logs were 100% preserved during biometrics restore.")

    # 6. Restore System backup:
    # Must restore system logs (log 1000 was not in system backup, so it reverts),
    # BUT student 999 MUST REMAIN intact!
    ok2, msg2 = restore_system_backup(sys_zip, create_safety_snapshot=False)
    assert ok2, f"System restore failed: {msg2}"
    print("  [PASS] System restore completed:", msg2)

    s_exists = conn.execute("SELECT COUNT(*) FROM students WHERE id = 999").fetchone()[0]
    assert s_exists == 1, "Enrolled student 999 was wiped out during system restore!"
    print("  [PASS] Enrolled students were 100% preserved during system restore.")

    # Cleanup test records and zip files
    conn.execute("DELETE FROM students WHERE id = 999")
    conn.execute("DELETE FROM attendance_logs WHERE id IN (999, 1000)")
    conn.commit()
    conn.close()

    if os.path.exists(bio_zip):
        os.remove(bio_zip)
    if os.path.exists(sys_zip):
        os.remove(sys_zip)

    print("=" * 60)
    print("  ALL SEPARATED BACKUP & RESTORE TESTS PASSED SUCCESSFULLY!")
    print("=" * 60)

if __name__ == "__main__":
    run_test()

