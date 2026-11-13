"""
SMART ENTRY - Test Guest Enrollment with Auto ID Generation
"""
import os
import sys
import json
import shutil
import cv2
import numpy as np

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from app import create_app, _seed_default_admin
from database.database import init_db, get_student_by_student_id, delete_student, get_all_students
from config import Config

def test_guest_enrollment():
    print("=" * 60)
    print("Testing Guest Enrollment with No ID Requirement")
    print("=" * 60)

    init_db()
    app = create_app()
    app.config["TESTING"] = True
    _seed_default_admin(app)

    with app.test_client() as client:
        # 1. Login
        login_res = client.post("/login", data={
            "username": "admin",
            "password": "smart_entry_2026"
        }, follow_redirects=True)
        assert login_res.status_code == 200

        # 2. Test Student validation: student_id is required
        res_fail = client.post("/admin/enroll/create", data={
            "full_name": "Test Student Missing ID",
            "student_id": "",
            "program": "BSIT",
            "user_type": "student"
        })
        assert res_fail.status_code == 400
        assert "ID is required" in res_fail.get_json()["message"]
        print("  [PASS] Student enrollment without ID correctly rejected.")

        # 2b. Test Student ID character limit: > 10 chars rejected
        res_long_id = client.post("/admin/enroll/create", data={
            "first_name": "John",
            "last_name": "Doe",
            "full_name": "John Doe",
            "student_id": "12345678901",  # 11 chars
            "program": "BSIT",
            "user_type": "student"
        })
        assert res_long_id.status_code == 400
        assert "cannot exceed 10 characters" in res_long_id.get_json()["message"]
        print("  [PASS] Student ID exceeding 10 characters correctly rejected.")

        # 2c. Test Student ID character limit: exactly 10 chars accepted
        res_valid_10 = client.post("/admin/enroll/create", data={
            "first_name": "John",
            "last_name": "Dela Cruz",
            "full_name": "John Dela Cruz",
            "student_id": "211-00123A",  # 10 chars
            "program": "BSIT",
            "user_type": "student"
        })
        assert res_valid_10.status_code == 200, f"Expected 200 for 10-char ID: {res_valid_10.data}"
        stage_token = res_valid_10.get_json()["enroll_token"]
        stage_dir = os.path.join(Config.FACE_DATA_DIR, "staging", stage_token)
        if os.path.exists(stage_dir):
            shutil.rmtree(stage_dir, ignore_errors=True)
        print("  [PASS] Student ID with exactly 10 characters accepted.")

        # 3. Test Guest enrollment: student_id is empty -> auto-generated!
        guest_name = "Test Guest Visitor"
        res_guest = client.post("/admin/enroll/create", data={
            "full_name": guest_name,
            "student_id": "",  # NO ID PROVIDED!
            "program": "Guest",
            "user_type": "guest"
        })
        assert res_guest.status_code == 200, f"Guest creation failed: {res_guest.data}"
        data = res_guest.get_json()
        assert data["success"] is True
        assert data["is_guest"] is True
        assert data["student_id"].startswith("GST-")
        auto_id = data["student_id"]
        enroll_token = data["enroll_token"]
        print(f"  [PASS] Guest enrollment initialized without ID! Auto-assigned ID: {auto_id}")

        # Clean up staging folder
        stage_dir = os.path.join(Config.FACE_DATA_DIR, "staging", enroll_token)
        if os.path.exists(stage_dir):
            shutil.rmtree(stage_dir, ignore_errors=True)

    print("=" * 60)
    print("Guest Enrollment API Test PASSED Successfully!")
    print("=" * 60)

if __name__ == "__main__":
    test_guest_enrollment()

