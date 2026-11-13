import os
import sys
import numpy as np
from playwright.sync_api import sync_playwright

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config import Config
import database.database as db
from recognition.image_crypto import save_encrypted_image

# 1. Setup test alerts
os.makedirs(Config.ALERTS_SNAPSHOT_DIR, exist_ok=True)
frame = np.zeros((100, 100, 3), dtype=np.uint8)
frame[:, :] = [30, 160, 70] # CSUCC green

snap_active = "verify_test_active.enc"
snap_res = "verify_test_resolved.enc"

path_active = os.path.join(Config.ALERTS_SNAPSHOT_DIR, snap_active)
path_res = os.path.join(Config.ALERTS_SNAPSHOT_DIR, snap_res)

save_encrypted_image(path_active, frame)
save_encrypted_image(path_res, frame)

id_active = db.log_alert(snapshot_path=f"snapshots/{snap_active}", confidence_score=0.35)
id_res = db.log_alert(snapshot_path=f"snapshots/{snap_res}", confidence_score=0.28)
db.resolve_alert(id_res)

try:
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        page.goto("http://localhost:5000/login")
        page.fill("input[name=username]", "admin")
        page.fill("input[name=password]", "smart_entry_2026")
        page.click("button[type=submit]")
        page.wait_for_load_state("networkidle")

        native_dialogs = []
        page.on("dialog", lambda d: (native_dialogs.append(d.message), d.dismiss()))

        # ── Test 1: Active Alerts Page ────────────────────────────────
        page.goto("http://localhost:5000/admin/alerts")
        page.wait_for_load_state("networkidle")
        active_imgs = page.query_selector_all("img.snapshot-thumb")
        print(f"[TEST 1] Active alerts snapshot count: {len(active_imgs)}")
        assert len(active_imgs) > 0, "Active alerts must display snapshot thumbnails"
        nw = active_imgs[0].evaluate("el => el.naturalWidth")
        print(f"  -> Thumbnail image naturalWidth: {nw} (Decrypted successfully in memory)")
        assert nw > 0, "Decrypted snapshot must render with naturalWidth > 0"

        # Click Resolve All button
        btn_resolve_all = page.query_selector('form[action*="resolve_all"] button')
        assert btn_resolve_all is not None, "Resolve All button must be visible"
        print("  -> Clicking 'Resolve All' button...")
        btn_resolve_all.click()
        page.wait_for_timeout(400)
        csucc_modal = page.query_selector("#csuccDialogOverlay:not(.hidden)")
        assert csucc_modal is not None, "Custom Athenaeum confirmation modal MUST open"
        modal_title = page.inner_text("#csuccDialogTitle")
        modal_msg = page.inner_text("#csuccDialogMessage")
        print(f"  -> Custom Modal Visible: True | Title: '{modal_title}' | Message: '{modal_msg}'")

        # Cancel modal
        page.click("#csuccDialogCancelBtn")
        page.wait_for_timeout(300)

        # ── Test 2: Resolved Alerts Page ──────────────────────────────
        page.goto("http://localhost:5000/admin/alerts/resolved")
        page.wait_for_load_state("networkidle")
        res_imgs = page.query_selector_all("img.snapshot-thumb")
        print(f"[TEST 2] Resolved alerts snapshot count: {len(res_imgs)}")
        assert len(res_imgs) > 0, "Resolved alerts must display snapshot thumbnails"

        # Click Clear All button
        btn_clear_all = page.query_selector('form[action*="delete_all_resolved"] button')
        assert btn_clear_all is not None, "Clear All button must be visible"
        print("  -> Clicking 'Clear All' button...")
        btn_clear_all.click()
        page.wait_for_timeout(400)
        csucc_modal_2 = page.query_selector("#csuccDialogOverlay:not(.hidden)")
        assert csucc_modal_2 is not None, "Custom Athenaeum modal MUST open for Clear All"
        modal_title_2 = page.inner_text("#csuccDialogTitle")
        modal_msg_2 = page.inner_text("#csuccDialogMessage")
        print(f"  -> Custom Modal Visible: True | Title: '{modal_title_2}' | Message: '{modal_msg_2}'")

        # Confirm that NO native browser dialogs appeared
        print(f"[TEST 3] Native browser popups intercepted: {native_dialogs}")
        assert len(native_dialogs) == 0, "NO native browser confirm() popups are allowed to trigger!"

        browser.close()
        print("\n=======================================================")
        print("  ALL ALERT THUMBNAIL & DIALOG VERIFICATIONS PASSED!")
        print("=======================================================")

finally:
    db.delete_alert(id_active)
    db.delete_alert(id_res)
    for p in [path_active, path_res]:
        if os.path.exists(p):
            os.remove(p)
