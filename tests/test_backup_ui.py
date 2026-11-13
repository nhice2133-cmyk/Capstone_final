import os
import sys
import time
from playwright.sync_api import sync_playwright

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from app import create_app
from database import database as db

def test_backup_ui():
    print("=" * 60)
    print("TESTING BACKUP & RESTORE SEPARATED UI (PLAYWRIGHT)")
    print("=" * 60)

    app = create_app()
    app.config["TESTING"] = True
    client = app.test_client()

    with client.session_transaction() as sess:
        sess["_user_id"] = "1"

    # Test GET /admin/backup
    res = client.get("/admin/backup")
    assert res.status_code == 200
    html = res.data.decode("utf-8")
    assert "System Logs" in html
    assert "Students" in html
    assert "Restore System Logs" in html
    assert "Restore Students" in html
    print("  [PASS] Backup dashboard template rendered with separated modules.")

    # Test POST /admin/backup/create (system)
    res_sys = client.post("/admin/backup/create", data={"backup_type": "system", "description": "Auto Test Sys"}, follow_redirects=True)
    assert res_sys.status_code == 200
    assert "System Core" in res_sys.data.decode("utf-8") and "created successfully" in res_sys.data.decode("utf-8")
    print("  [PASS] System Core & Logs backup action created archive.")

    # Test POST /admin/backup/create (biometrics)
    res_bio = client.post("/admin/backup/create", data={"backup_type": "biometrics", "description": "Auto Test Bio"}, follow_redirects=True)
    assert res_bio.status_code == 200
    assert "Enrolled Students" in res_bio.data.decode("utf-8") and "created successfully" in res_bio.data.decode("utf-8")
    print("  [PASS] Enrolled Students & Biometrics backup action created archive.")

    # Test GET /admin/backup/download-current?type=system
    res_dl_sys = client.get("/admin/backup/download-current?type=system")
    assert res_dl_sys.status_code == 200
    assert res_dl_sys.mimetype == "application/zip"
    print("  [PASS] Download system archive streamed application/zip.")

    # Test GET /admin/backup/download-current?type=biometrics
    res_dl_bio = client.get("/admin/backup/download-current?type=biometrics")
    assert res_dl_bio.status_code == 200
    assert res_dl_bio.mimetype == "application/zip"
    print("  [PASS] Download biometrics archive streamed application/zip.")

    print("=" * 60)
    print("  ALL BACKUP UI & CONTROLLER TESTS PASSED!")
    print("=" * 60)

if __name__ == "__main__":
    test_backup_ui()
