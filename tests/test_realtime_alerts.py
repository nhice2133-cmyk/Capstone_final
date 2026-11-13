import time
import os
import sys
import numpy as np
from playwright.sync_api import sync_playwright

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config import Config
import database.database as db
from recognition.image_crypto import save_encrypted_image

def test_realtime_alerts():
    print("=" * 70)
    print("  TESTING REAL-TIME ALERTS UPDATE IN BROWSER")
    print("=" * 70)

    # 1. Prepare a new test alert snapshot
    snap_name = "test_live_realtime_alert.enc"
    snap_path = os.path.join(Config.ALERTS_SNAPSHOT_DIR, snap_name)
    test_img = np.zeros((100, 100, 3), dtype=np.uint8)
    test_img[:, :] = [0, 0, 255] # Red test frame
    save_encrypted_image(snap_path, test_img)

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()

        # Login
        page.goto("http://localhost:5000/login")
        page.fill("input[name=username]", "admin")
        page.fill("input[name=password]", "smart_entry_2026")
        page.click("button[type=submit]")
        page.wait_for_load_state("networkidle")

        # Open alerts page
        page.goto("http://localhost:5000/admin/alerts")
        page.wait_for_load_state("networkidle")

        initial_count = len(page.query_selector_all("#alertsTableBody tr[data-alert-id]"))
        print(f"[Step 1] Initial rows in table: {initial_count}")

        # Check LIVE indicator
        indicator = page.query_selector("#liveAlertsIndicator")
        assert indicator is not None, "Live indicator badge must exist"
        print("  -> Live monitoring indicator present in toolbar.")

        # 2. Insert an alert into the database behind the scenes (simulating kiosk unknown detection)
        new_alert_id = db.log_alert(
            snapshot_path=f"snapshots/{snap_name}",
            confidence_score=0.15
        )
        print(f"[Step 2] Background kiosk detected stranger! Logged new alert #{new_alert_id}.")

        # 3. Wait for real-time polling to detect and dynamically insert the new row
        print("[Step 3] Waiting for real-time live update in browser (up to 4.5 seconds)...")
        new_row_selector = f"#alertRow-{new_alert_id}"
        page.wait_for_selector(new_row_selector, timeout=6000)

        updated_count = len(page.query_selector_all("#alertsTableBody tr[data-alert-id]"))
        print(f"  -> SUCCESS! New alert row dynamically rendered: {new_row_selector}")
        print(f"  -> Updated row count: {updated_count} (was {initial_count})")
        assert updated_count == initial_count + 1, "Row count must increment by 1"

        # Check that the image in the new row is loaded and decrypted
        new_img = page.query_selector(f"{new_row_selector} img.snapshot-thumb")
        assert new_img is not None, "Snapshot thumbnail must exist in dynamic row"
        nw = new_img.evaluate("el => el.naturalWidth")
        print(f"  -> Dynamic thumbnail decrypted in memory: naturalWidth={nw}")
        assert nw > 0, "Decrypted thumbnail must render properly"

        # 4. Test AJAX resolve without page reload
        print("\n[Step 4] Testing AJAX resolve button on newly arrived alert...")
        resolve_btn = page.query_selector(f"{new_row_selector} .btn-resolve-ajax")
        assert resolve_btn is not None, "AJAX resolve button must exist"
        resolve_btn.click()

        # Wait for row to be removed from DOM
        page.wait_for_selector(new_row_selector, state="detached", timeout=3000)
        final_count = len(page.query_selector_all("#alertsTableBody tr[data-alert-id]"))
        print(f"  -> SUCCESS! Alert #{new_alert_id} resolved via AJAX and smoothly removed from DOM.")
        print(f"  -> Final table count: {final_count} (returned to {initial_count})")
        assert final_count == initial_count, "Row count must return to initial count"

        browser.close()

    # Cleanup test snapshot file
    if os.path.exists(snap_path):
        os.remove(snap_path)

    print("\n" + "=" * 70)
    print("  ALL REAL-TIME ALERTS AUTOMATION TESTS PASSED 100%!")
    print("=" * 70)

if __name__ == "__main__":
    test_realtime_alerts()

