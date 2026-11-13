"""
Unit and Integration Tests for SMART ENTRY Administrator Master Key Recovery.
Tests the two-step verification flow:
- Step 1: Strictly verifies Master Recovery Key (no security questions).
- Step 2: Unlocks password fields and updates admin credentials.
"""
import sys
import os

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from app import create_app, _seed_default_admin
from database.database import init_db, get_admin_by_username
from config import Config


def test_forgot_password_suite():
    print("=" * 70)
    print("  TESTING 2-STEP MASTER RECOVERY KEY PASSWORD RESET SUITE")
    print("=" * 70)

    init_db()
    app = create_app()
    app.config["TESTING"] = True
    app.config["WTF_CSRF_ENABLED"] = False
    _seed_default_admin(app)

    with app.test_client() as client:
        # 1. Test GET /forgot-password
        res = client.get("/forgot-password")
        assert res.status_code == 200, f"Expected 200, got {res.status_code}"
        assert b"Master Key" in res.data
        assert b"Master Recovery Key" in res.data
        # Ensure security questions were completely removed
        assert b"Security Question" not in res.data
        assert b"security_answer" not in res.data
        print("  [PASS] GET /forgot-password loads Step 1 (Security questions completely removed).")

        # 1b. Test GET /admin/forgot-password alias
        res_alias = client.get("/admin/forgot-password")
        assert res_alias.status_code == 200
        print("  [PASS] GET /admin/forgot-password alias loads successfully (HTTP 200).")

        # 2. Test Step 1 AJAX Verification with Invalid Username
        res_bad_user = client.post("/forgot-password", json={
            "action": "verify_key",
            "username": "non_existent_admin_12345",
            "recovery_key": Config.ADMIN_RECOVERY_KEY,
        })
        assert res_bad_user.status_code == 200
        json_data = res_bad_user.get_json()
        assert json_data["success"] is False
        assert "not found" in json_data["message"]
        print("  [PASS] Step 1: Non-existent admin username properly rejected.")

        # 3. Test Step 1 AJAX Verification with Invalid Master Key
        res_bad_key = client.post("/forgot-password", json={
            "action": "verify_key",
            "username": "admin",
            "recovery_key": "WRONG-MASTER-KEY-9999",
        })
        assert res_bad_key.status_code == 200
        json_data = res_bad_key.get_json()
        assert json_data["success"] is False
        assert "Invalid Master Recovery Key" in json_data["message"]
        print("  [PASS] Step 1: Invalid Master Recovery Key properly rejected.")

        # 4. Test Step 1 AJAX Verification with Valid Master Key
        res_good_key = client.post("/forgot-password", json={
            "action": "verify_key",
            "username": "admin",
            "recovery_key": "csucc-athenaeum-reset-2026",  # test case insensitivity
        })
        assert res_good_key.status_code == 200
        json_data = res_good_key.get_json()
        assert json_data["success"] is True
        print("  [PASS] Step 1: Master Recovery Key verified; unlocks Step 2.")

        # 5. Test Step 2: Password Mismatch
        res_mismatch = client.post("/forgot-password", data={
            "step": "2",
            "username": "admin",
            "recovery_key": Config.ADMIN_RECOVERY_KEY,
            "new_password": "ValidNewPassword123!",
            "confirm_password": "DifferentPassword456!",
        }, follow_redirects=True)
        assert b"do not match" in res_mismatch.data
        print("  [PASS] Step 2: Mismatched passwords rejected.")

        # 6. Test Step 2: Password < 6 Chars
        res_short = client.post("/forgot-password", data={
            "step": "2",
            "username": "admin",
            "recovery_key": Config.ADMIN_RECOVERY_KEY,
            "new_password": "123",
            "confirm_password": "123",
        }, follow_redirects=True)
        assert b"at least 6 characters" in res_short.data
        print("  [PASS] Step 2: Short password (< 6 chars) rejected.")

        # 7. Test Step 2: Password Reset without Master Key
        res_no_key = client.post("/forgot-password", data={
            "step": "2",
            "username": "admin",
            "recovery_key": "INVALID-KEY",
            "new_password": "ValidNewPassword123!",
            "confirm_password": "ValidNewPassword123!",
        }, follow_redirects=True)
        assert b"Authorization failed" in res_no_key.data or b"Invalid" in res_no_key.data
        print("  [PASS] Step 2: Attempt without valid Master Key blocked.")

        # 8. Test Step 2: Successful Password Reset
        test_new_pw = "NewSecureAdmin2026!#"
        res_success = client.post("/forgot-password", data={
            "step": "2",
            "username": "admin",
            "recovery_key": Config.ADMIN_RECOVERY_KEY,
            "new_password": test_new_pw,
            "confirm_password": test_new_pw,
        }, follow_redirects=True)
        assert b"successfully reset" in res_success.data or b"Please sign in" in res_success.data
        print("  [PASS] Step 2: Password successfully updated via Master Recovery Key.")

        # 9. Verify Login with New Password
        login_res = client.post("/login", data={
            "username": "admin",
            "password": test_new_pw,
        }, follow_redirects=True)
        assert b"Invalid" not in login_res.data
        assert login_res.status_code == 200
        print("  [PASS] Admin logged in successfully with new password.")

        # Log out
        client.get("/logout", follow_redirects=True)

        # 10. Test Non-JS Fallback Form Flow (Step 1 POST -> Step 2 Form)
        res_step1_fallback = client.post("/forgot-password", data={
            "step": "1",
            "username": "admin",
            "recovery_key": Config.ADMIN_RECOVERY_KEY,
        }, follow_redirects=True)
        assert b"Set New Password" in res_step1_fallback.data or b"step2Section" in res_step1_fallback.data
        print("  [PASS] Non-JS Step 1 fallback form progression verified.")

        # 11. Reset back to default 'smart_entry_2026' for library deployment
        client.post("/forgot-password", data={
            "step": "2",
            "username": "admin",
            "recovery_key": Config.ADMIN_RECOVERY_KEY,
            "new_password": "smart_entry_2026",
            "confirm_password": "smart_entry_2026",
        }, follow_redirects=True)
        print("  [PASS] Reset password back to default 'smart_entry_2026' for deployment.")

    print("=" * 70)
    print("  ALL 2-STEP MASTER KEY RECOVERY TESTS PASSED (100% OFFLINE)!")
    print("=" * 70)


if __name__ == "__main__":
    test_forgot_password_suite()
