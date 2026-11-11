"""
Test suite to verify that:
1. Student is NOT enrolled in DB in Step 1.
2. Incomplete image capture (<20 images) is rejected.
3. Student is ONLY inserted into DB after successfully capturing all 20 images.
4. Duplicate enrollment by Student ID (case-insensitive and trimmed) is blocked.
5. Duplicate enrollment by Full Name (case-insensitive and trimmed) is blocked.
"""
import os
import sys
import cv2
import json
import base64
import shutil

# Ensure workspace root is in sys.path
BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from app import create_app
from database import database as db

app = create_app()
client = app.test_client()

# Clean up test IDs
conn = db.get_db_connection()
rows = conn.execute("SELECT id FROM students WHERE student_id IN ('2024-0001', '2024-9999')").fetchall()
for r in rows:
    conn.execute("DELETE FROM students WHERE id = ?", (r["id"],))
    if os.path.exists(f"face_data/{r['id']}"):
        shutil.rmtree(f"face_data/{r['id']}")
conn.commit()
conn.close()

with client:
    # 1. Login admin
    client.post("/login", data={"username": "admin", "password": "smart_entry_2026"})

    print("=== TEST 1: Step 1 Validation (No Student Record in DB) ===")
    res1 = client.post("/admin/enroll/create", data={
        "full_name": "Maria Santos",
        "student_id": "2024-0001",
        "program": "BSCS"
    })
    print("Step 1 response:", res1.status_code, res1.get_json())
    assert res1.status_code == 200
    token = res1.get_json()["enroll_token"]

    # Verify Maria Santos is NOT in the database yet
    conn = db.get_db_connection()
    st_check1 = conn.execute("SELECT * FROM students WHERE student_id = '2024-0001'").fetchone()
    conn.close()
    assert st_check1 is None, "ERROR: Student was inserted into DB during Step 1!"
    print("PASS: Student is NOT in DB after Step 1.")

    print("\n=== TEST 2: Incomplete Image Capture Rejection (5 images only) ===")
    sample_img = cv2.imread("recognition/evaluation/benchmark_dataset/s3/1.pgm")
    for i in range(5):
        shifted = cv2.convertScaleAbs(sample_img, alpha=1.0, beta=i * 6)
        _, buf = cv2.imencode(".jpg", shifted)
        b64 = "data:image/jpeg;base64," + base64.b64encode(buf).decode("utf-8")
        r_cap = client.post("/admin/enroll/capture", json={
            "enroll_token": token,
            "image": b64,
            "img_index": i
        })
        assert r_cap.get_json()["success"] is True, f"Capture failed at index {i}"

    # Attempt to finalize with only 5 images
    r_early = client.post("/admin/enroll/train", json={"enroll_token": token})
    print("Early finalize response:", r_early.status_code, r_early.get_json())
    assert r_early.status_code == 400
    assert "Cannot enroll student" in r_early.get_json()["message"]

    # Student still must NOT be in DB
    conn = db.get_db_connection()
    st_check2 = conn.execute("SELECT * FROM students WHERE student_id = '2024-0001'").fetchone()
    conn.close()
    assert st_check2 is None, "ERROR: Student was enrolled with only 5 images!"
    print("PASS: Incomplete capture correctly rejected; student not enrolled.")

    print("\n=== TEST 3: Capture Remaining 15 Images and Complete Enrollment ===")
    from recognition.face_detection import FaceDetector
    fd = FaceDetector()
    s3_dir = "recognition/evaluation/benchmark_dataset/s3"
    valid_face_imgs = []
    for f in sorted(os.listdir(s3_dir)):
        if f.endswith(".pgm"):
            im = cv2.imread(os.path.join(s3_dir, f))
            faces, _ = fd.detect(im)
            if len(faces) == 1:
                valid_face_imgs.append(im)
    
    for i in range(5, 20):
        # Pick from valid face images
        img_f = valid_face_imgs[(i - 5) % len(valid_face_imgs)].copy()
        if i >= 13:
            img_f = cv2.convertScaleAbs(img_f, alpha=1.01, beta=(i - 12) * 2)
        _, buf = cv2.imencode(".jpg", img_f)
        b64 = "data:image/jpeg;base64," + base64.b64encode(buf).decode("utf-8")
        r_cap = client.post("/admin/enroll/capture", json={
            "enroll_token": token,
            "image": b64,
            "img_index": i
        })
        assert r_cap.get_json()["success"] is True, f"Capture failed at index {i}: {r_cap.get_json()}"

    # Now finalize with all 20 images captured
    r_final = client.post("/admin/enroll/train", json={"enroll_token": token})
    print("Finalize response:", r_final.status_code, r_final.get_json())
    assert r_final.status_code == 200
    assert r_final.get_json()["success"] is True

    # Student MUST now exist in DB!
    conn = db.get_db_connection()
    st_check3 = conn.execute("SELECT * FROM students WHERE student_id = '2024-0001'").fetchone()
    conn.close()
    assert st_check3 is not None, "ERROR: Student was not inserted into DB upon finalization!"
    print("PASS: Student successfully enrolled in DB after 20 images:", dict(st_check3))
    new_id = st_check3["id"]

    # Verify permanent folder has all 20 images
    perm_images = os.listdir(f"face_data/{new_id}")
    assert len(perm_images) == 20
    print(f"PASS: Permanent face_data/{new_id} contains all {len(perm_images)} images.")

    print("\n=== TEST 4: Prevent Duplicate Enrollment by ID ===")
    r_dup_id = client.post("/admin/enroll/create", data={
        "full_name": "Another Student",
        "student_id": " 2024-0001 ",
        "program": "BSIT"
    })
    print("Duplicate ID response:", r_dup_id.status_code, r_dup_id.get_json())
    assert r_dup_id.status_code == 409
    assert "already enrolled" in r_dup_id.get_json()["message"]
    print("PASS: Duplicate Student ID blocked.")

    print("\n=== TEST 5: Prevent Duplicate Enrollment by Name ===")
    r_dup_name = client.post("/admin/enroll/create", data={
        "full_name": "maria santos",
        "student_id": "2024-9999",
        "program": "BSIT"
    })
    print("Duplicate Name response:", r_dup_name.status_code, r_dup_name.get_json())
    assert r_dup_name.status_code == 409
    assert "already enrolled" in r_dup_name.get_json()["message"]
    print("PASS: Duplicate Full Name blocked.")

    # Clean up test student
    conn = db.get_db_connection()
    conn.execute("DELETE FROM students WHERE id = ?", (new_id,))
    conn.commit()
    conn.close()
    if os.path.exists(f"face_data/{new_id}"):
        shutil.rmtree(f"face_data/{new_id}")

    print("\nALL 5 WORKFLOW TESTS PASSED SUCCESSFULLY!")
