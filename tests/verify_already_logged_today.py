import os
import sys
import time

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from datetime import datetime
from config import Config
from database import database as db
from playwright.sync_api import sync_playwright

def test_already_logged_feature():
    print("=" * 70)
    print("  TESTING 'ALREADY LOGGED TODAY' FEATURE AND AUTO MOVE-ON")
    print("=" * 70)

    # 1. Clean DB state
    db.init_db()
    conn = db.get_db_connection()
    conn.execute("DELETE FROM attendance_logs")
    conn.execute("DELETE FROM students WHERE student_id = '2026-0500'")
    conn.commit()
    conn.close()

    # 2. Create student
    student_db_id = db.create_student("Angelo Cruz", "2026-0500", "BSCS")
    print(f"\n[Step 1] Created student 'Angelo Cruz' (DB ID: {student_db_id})")

    # 3. Verify no log exists for today
    log_before = db.get_today_attendance_log(student_db_id)
    assert log_before is None, "Log before Time In should be None"
    print("  -> Confirmed: No attendance log before entry today.")

    # 4. First Time In logging
    rec_id = db.log_time_in(student_db_id, "Study Room", node="entry")
    print(f"\n[Step 2] Logged initial Time In today. Record ID: {rec_id}")

    # 5. Verify get_today_attendance_log returns the record
    today_log = db.get_today_attendance_log(student_db_id)
    assert today_log is not None, "Today's log must be found after logging Time In"
    assert today_log["student_db_id"] == student_db_id
    assert today_log["visit_purpose"] == "Study Room"
    print(f"  -> Today's attendance retrieved: time_in={today_log['time_in']}, purpose={today_log['visit_purpose']}")

    # 6. Test duplicate prevention on POST /kiosk/log_entry
    from app import create_app
    app = create_app()
    with app.test_client() as client:
        # Simulate /kiosk/log_entry when already logged
        resp = client.post("/kiosk/log_entry", json={
            "student_db_id": student_db_id,
            "visit_purpose": "Borrow Book"
        })
        json_data = resp.get_json()
        print(f"\n[Step 3] Duplicate /kiosk/log_entry attempt response: {json_data}")
        assert json_data["already_logged"] is True, "Backend must report already_logged=True"

    # Confirm only 1 log exists
    conn = db.get_db_connection()
    c = conn.execute("SELECT COUNT(*) FROM attendance_logs WHERE student_db_id = ?", (student_db_id,)).fetchone()[0]
    conn.close()
    assert c == 1, f"Expected exactly 1 attendance log, got {c}"
    print(f"  -> Total logs in DB for Angelo: {c} (No duplicate record created)")

    # 7. Test Kiosk Web UI with Playwright
    print("\n[Step 4] Testing Kiosk Web UI Display & Automatic Move-On via Playwright...")
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        page.goto("http://localhost:5000/kiosk")
        page.wait_for_load_state("networkidle")

        # Verify #stateAlreadyLogged DOM structure
        already_el = page.query_selector("#stateAlreadyLogged")
        assert already_el is not None, "#stateAlreadyLogged element must exist in DOM"
        print("  -> #stateAlreadyLogged element exists in DOM.")

        # Simulate recognition event returning status: "already_logged"
        mock_payload = {
            "status": "already_logged",
            "student_db_id": student_db_id,
            "full_name": "Angelo Cruz",
            "student_id": "2026-0500",
            "program": "BSCS",
            "time_in": "08:15:30",
            "visit_purpose": "Study Room",
            "face_box": {"x": 0.3, "y": 0.2, "w": 0.4, "h": 0.5}
        }
        page.evaluate("(data) => handleRecognitionResult(data)", mock_payload)

        # Check visibility
        is_visible = page.evaluate("() => !document.getElementById('stateAlreadyLogged').classList.contains('hidden')")
        print(f"  -> #stateAlreadyLogged is visible: {is_visible}")
        assert is_visible is True, "stateAlreadyLogged should be visible"

        name_text = page.inner_text("#alreadyLoggedName")
        details_text = page.inner_text("#alreadyLoggedDetails")
        time_text = page.inner_text("#alreadyLoggedTime")
        print(f"  -> Displayed Name: '{name_text}'")
        print(f"  -> Displayed Details: '{details_text}'")
        print(f"  -> Displayed Time In: '{time_text}'")

        assert "Angelo Cruz" in name_text
        # Check that Program is displayed and Student ID is NEVER exposed (Data Privacy Act)
        assert "BSCS" in details_text
        assert "2026-0500" not in details_text
        assert "8:15 AM" in time_text

        # Verify "Move On": wait 3.2 seconds and verify it automatically resets to default/idle state
        print("  -> Waiting for auto move-on timer (3.2 seconds)...")
        page.wait_for_timeout(3200)

        is_default_visible = page.evaluate("() => !document.getElementById('stateDefault').classList.contains('hidden')")
        is_already_hidden = page.evaluate("() => document.getElementById('stateAlreadyLogged').classList.contains('hidden')")
        print(f"  -> Reset to Default state visible: {is_default_visible}")
        print(f"  -> Already Logged state hidden: {is_already_hidden}")
        assert is_default_visible is True, "Must reset to default scanning state"
        assert is_already_hidden is True, "Already logged state must be hidden after reset"

        browser.close()

    # 8. Clean up
    conn = db.get_db_connection()
    conn.execute("DELETE FROM attendance_logs WHERE student_db_id = ?", (student_db_id,))
    conn.execute("DELETE FROM students WHERE id = ?", (student_db_id,))
    conn.commit()
    conn.close()

    print("\n" + "=" * 70)
    print("  ALL 'ALREADY LOGGED TODAY' TESTS COMPLETED AND PASSED!")
    print("=" * 70)

if __name__ == "__main__":
    test_already_logged_feature()

