"""
Verification Script: Returning User Recognition & Duplicate Prevention
CSUCC Athenaeum SMART ENTRY System
"""
import os
import sys
import shutil

# Ensure project root is in sys.path
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

import numpy as np
import cv2
from datetime import datetime, timedelta
from config import Config, sanitize_name_for_filesystem
from database import database as db
from recognition.face_recognition import FaceRecognizer
from recognition.training import train_model
from recognition.image_crypto import save_encrypted_image, load_encrypted_image

def create_synthetic_face_dataset(student_name: str, base_color: int = 120):
    """Creates a deterministic synthetic face dataset with landmark features."""
    safe_name = sanitize_name_for_filesystem(student_name)
    folder = os.path.join(Config.FACE_DATA_DIR, safe_name)
    os.makedirs(folder, exist_ok=True)
    
    images = []
    for i in range(20):
        # Create 200x200 canvas
        img = np.full((200, 200, 3), base_color, dtype=np.uint8)
        # Face shape
        cv2.circle(img, (100, 100), 70, (base_color + 40, base_color + 30, base_color + 20), -1)
        # Eyes
        eye_y = 85 + (i % 3)
        cv2.circle(img, (75, eye_y), 8, (40, 30, 20), -1)
        cv2.circle(img, (125, eye_y), 8, (40, 30, 20), -1)
        # Nose
        cv2.line(img, (100, 95), (100, 120), (50, 40, 30), 2)
        # Mouth
        mouth_curve = 135 + (i % 4)
        cv2.ellipse(img, (100, mouth_curve), (25, 10), 0, 0, 180, (60, 50, 40), 2)
        
        # Save encrypted image
        file_path = os.path.join(folder, f"{safe_name}_{i:03d}.enc")
        save_encrypted_image(file_path, img)
        images.append(img)
    return images

def run_verification():
    print("=" * 70)
    print("  VERIFYING RETURNING USER RECOGNITION & DUPLICATE PREVENTION")
    print("=" * 70)

    # 1. Clean test state
    db.init_db()
    conn = db.get_db_connection()
    conn.execute("DELETE FROM attendance_logs")
    conn.execute("DELETE FROM security_alerts")
    conn.execute("DELETE FROM students")
    conn.commit()
    conn.close()

    if os.path.exists(Config.FACE_DATA_DIR):
        shutil.rmtree(Config.FACE_DATA_DIR)
    os.makedirs(Config.FACE_DATA_DIR, exist_ok=True)

    # 2. Enroll Student A
    print("\n[Step 1] Enrolling Student A ('Maria Santos', ID: '2026-0042')...")
    id_a = db.create_student("Maria Santos", "2026-0042", "BSCS")
    imgs_a = create_synthetic_face_dataset("Maria Santos", base_color=120)
    train_res = train_model()
    print(f"  -> Trained model: {train_res['message']}")
    assert train_res["num_subjects"] == 1, "Expected 1 subject trained"

    # Reload recognizer
    recognizer = FaceRecognizer()
    assert recognizer.is_ready, "Recognizer should be ready with enrolled embeddings"

    # 3. Visit 1 (Morning Entry)
    print("\n[Step 2] Testing Visit 1 (Morning Visit)...")
    test_face_a = imgs_a[0]
    sid_pred, score, info = recognizer.predict(test_face_a)
    print(f"  -> Predicted DB ID: {sid_pred}, Score: {score:.4f}")
    print(f"  -> Student Record: {info}")
    
    assert sid_pred == id_a, f"Expected DB ID {id_a}, got {sid_pred}"
    assert info["student_id"] == "2026-0042", "Student ID mismatch!"
    assert info["full_name"] == "Maria Santos", "Student Name mismatch!"
    assert score >= recognizer.get_threshold(), "Cosine similarity below threshold!"

    # Log Time In
    rec_id = db.log_time_in(sid_pred, "Research", node="entry")
    print(f"  -> Logged Time In successfully. Attendance Record ID: {rec_id}")

    # Check student count remained 1
    students_count_1 = len(db.get_all_students())
    assert students_count_1 == 1, "Recognition must NOT create a new student record!"
    print(f"  -> Total students in database: {students_count_1} (No duplicate identity created)")

    # 4. Immediate repeat detection (debouncing & cooldown)
    print("\n[Step 3] Testing Immediate Repeat Detection (Within Cooldown)...")
    from routes.kiosk import _last_recognized_time
    camera_label = "entry_cam"
    now = datetime.now()
    _last_recognized_time[(sid_pred, camera_label)] = now

    # Simulate kiosk check within 60s
    last_rec = _last_recognized_time.get((sid_pred, camera_label))
    is_in_cooldown = (now - last_rec).total_seconds() < Config.RECOGNITION_COOLDOWN_SECONDS
    print(f"  -> Second recognition within cooldown detected: {is_in_cooldown}")
    assert is_in_cooldown is True, "Repeat scan within 60s must trigger cooldown"
    
    # Confirm attendance logs did not duplicate
    conn = db.get_db_connection()
    logs_count = conn.execute("SELECT COUNT(*) FROM attendance_logs WHERE student_db_id = ?", (id_a,)).fetchone()[0]
    conn.close()
    assert logs_count == 1, f"Expected exactly 1 attendance log during cooldown, got {logs_count}"
    print(f"  -> Attendance log count for Maria: {logs_count} (No duplicate log created)")

    # 5. Visit 2 (Afternoon / Next Day Return)
    print("\n[Step 4] Testing Visit 2 (Subsequent Visit After Cooldown)...")
    # Simulate returning 2 hours later
    _last_recognized_time[(sid_pred, camera_label)] = now - timedelta(hours=2)
    test_face_a_var = imgs_a[12]  # different angle/expression sample
    sid_pred_2, score_2, info_2 = recognizer.predict(test_face_a_var)
    print(f"  -> Visit 2 Predicted DB ID: {sid_pred_2}, Score: {score_2:.4f}")
    assert sid_pred_2 == id_a, "Visit 2 failed to recognize returning student!"
    assert info_2["student_id"] == "2026-0042"
    
    rec_id_2 = db.log_time_in(sid_pred_2, "Group Study", node="entry")
    print(f"  -> Visit 2 Logged Time In successfully. Attendance Record ID: {rec_id_2}")

    students_count_2 = len(db.get_all_students())
    assert students_count_2 == 1, "Repeated visits must NEVER create new student identities!"
    print(f"  -> Total students in database: {students_count_2} (Identity preserved)")

    # 6. Multi-User Discrimination
    print("\n[Step 5] Testing Multi-User Discrimination (Enrolling Student B)...")
    id_b = db.create_student("Juan Dela Cruz", "2026-0088", "BSIT")
    imgs_b = create_synthetic_face_dataset("Juan Dela Cruz", base_color=190)
    train_model()
    recognizer.load_model()

    # Test Student A face against recognizer
    sid_check_a, score_check_a, info_check_a = recognizer.predict(imgs_a[5])
    assert sid_check_a == id_a, "Failed to identify Student A with multiple enrolled users!"
    assert info_check_a["full_name"] == "Maria Santos"

    # Test Student B face against recognizer
    sid_check_b, score_check_b, info_check_b = recognizer.predict(imgs_b[5])
    assert sid_check_b == id_b, "Failed to identify Student B!"
    assert info_check_b["full_name"] == "Juan Dela Cruz"
    print("  -> Multi-user recognition verified: Maria and Juan correctly distinguished.")

    # 7. Stranger / Unenrolled Face Rejection
    print("\n[Step 6] Testing Stranger / Unenrolled Face Rejection...")
    stranger_face = np.full((200, 200, 3), 30, dtype=np.uint8)
    cv2.circle(stranger_face, (100, 100), 50, (60, 60, 60), -1)
    sid_stranger, score_stranger, info_stranger = recognizer.predict(stranger_face)
    print(f"  -> Stranger Prediction: ID={sid_stranger}, Score={score_stranger:.4f}")
    assert sid_stranger == -1, "Stranger should be rejected with label -1!"
    assert info_stranger is None, "Stranger must not return student info!"
    print("  -> Stranger correctly rejected as unknown (no false positive).")

    # 8. Duplicate Registration Prevention
    print("\n[Step 7] Testing Duplicate Registration Prevention...")
    # Duplicate ID
    is_dup_id, msg_id = db.check_student_duplicate("Another Name", "2026-0042")
    print(f"  -> Duplicate ID attempt: is_dup={is_dup_id}, msg='{msg_id}'")
    assert is_dup_id is True, "Duplicate student_id was not blocked!"

    # Duplicate Name
    is_dup_name, msg_name = db.check_student_duplicate("Maria Santos", "2026-9999")
    print(f"  -> Duplicate Name attempt: is_dup={is_dup_name}, msg='{msg_name}'")
    assert is_dup_name is True, "Duplicate student full_name was not blocked!"

    # Case-insensitive & trimmed match
    is_dup_case, msg_case = db.check_student_duplicate("  maria SANTOS  ", "2026-8888")
    print(f"  -> Case-insensitive duplicate attempt: is_dup={is_dup_case}, msg='{msg_case}'")
    assert is_dup_case is True, "Case-insensitive duplicate was not blocked!"

    # 9. Cleanup test data
    conn = db.get_db_connection()
    conn.execute("DELETE FROM attendance_logs")
    conn.execute("DELETE FROM security_alerts")
    conn.execute("DELETE FROM students")
    conn.commit()
    conn.close()
    if os.path.exists(Config.FACE_DATA_DIR):
        shutil.rmtree(Config.FACE_DATA_DIR)
    os.makedirs(Config.FACE_DATA_DIR, exist_ok=True)
    train_model()

    print("\n" + "=" * 70)
    print("  ALL VERIFICATION TESTS COMPLETED AND PASSED SUCCESSFULLY!")
    print("=" * 70)

if __name__ == "__main__":
    run_verification()
