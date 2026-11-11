"""
SMART ENTRY — Student Management Routes
Face enrollment (staging capture -> 20 images verified -> atomic database enrollment & training) and CRUD.
"""
import os
import re
import cv2
import json
import time
import uuid
import shutil
import base64
import numpy as np
from flask import Blueprint, render_template, request, jsonify, redirect, url_for, flash
from flask_login import login_required
from database import database as db
from recognition.training import train_model
from recognition.face_detection import FaceDetector
from config import Config, sanitize_name_for_filesystem

students_bp = Blueprint("students", __name__)


# ── Student list & management ─────────────────────────────────────────────────

@students_bp.route("/admin/students")
@login_required
def list_students():
    students = db.get_all_students()
    return render_template("admin/students.html", students=students)


@students_bp.route("/admin/students/delete/<int:student_db_id>", methods=["GET", "POST"])
@login_required
def delete_student(student_db_id):
    if request.method == "GET":
        return redirect(url_for("students.list_students"))

    student_row = db.get_student_by_db_id(student_db_id)
    student = dict(student_row) if student_row else None
    name = student.get("full_name") if student else f"Student #{student_db_id}"
    
    # 1. Remove face data folder named by registered name (and legacy numerical id if any)
    if student and student.get("full_name"):
        raw_name = student["full_name"].strip()
        safe_name = sanitize_name_for_filesystem(raw_name)
        candidates = {
            os.path.join(Config.FACE_DATA_DIR, safe_name),
            os.path.join(Config.FACE_DATA_DIR, safe_name.replace(" ", "_")),
            os.path.join(Config.FACE_DATA_DIR, raw_name),
            os.path.join(Config.FACE_DATA_DIR, str(student_db_id)),
        }
        for d in candidates:
            if os.path.isdir(d):
                shutil.rmtree(d, ignore_errors=True)

    # 2. Delete student record from SQLite
    db.delete_student(student_db_id)
        
    # 3. Retrain to update model and remove student from label mapping
    train_result = train_model()
    msg = train_result.get("message", "") if isinstance(train_result, dict) else ""
    flash(f"Student '{name}' deleted successfully. {msg}".strip(), "success")
    return redirect(url_for("students.list_students"))


@students_bp.route("/admin/students/toggle/<int:student_db_id>", methods=["POST"])
@login_required
def toggle_student(student_db_id):
    student_row = db.get_student_by_db_id(student_db_id)
    student = dict(student_row) if student_row else None
    if student:
        new_status = "inactive" if student.get("status") == "active" else "active"
        db.update_student_status(student_db_id, new_status)
        # Retrain to exclude/include in active label mapping
        train_result = train_model()
        msg = train_result.get("message", "") if isinstance(train_result, dict) else ""
        flash(
            f"Student status updated to '{new_status}'. {msg}".strip(),
            "success",
        )
    return redirect(url_for("students.list_students"))


# ── Face Enrollment ───────────────────────────────────────────────────────────

@students_bp.route("/admin/enroll", methods=["GET"])
@login_required
def enroll_page():
    return render_template("admin/enrollment.html")


@students_bp.route("/admin/enroll/check_name", methods=["GET"])
@login_required
def check_name_availability():
    """Real-time validation and duplicate check for registered names."""
    first_name = request.args.get("first_name", "").strip()
    last_name = request.args.get("last_name", "").strip()
    full_name = request.args.get("full_name", "").strip()
    if not full_name and (first_name or last_name):
        full_name = f"{first_name} {last_name}".strip()

    if not full_name or len(full_name) < 2:
        return jsonify({"valid": False, "message": "Name must be at least 2 characters."})

    name_regex = re.compile(r"^[A-Za-zÀ-ÿñÑ\s\.\-']+$")
    if not name_regex.match(full_name):
        return jsonify({
            "valid": False,
            "message": "Name contains invalid characters (numbers or special symbols are not allowed)."
        })

    is_dup, dup_msg = db.check_student_duplicate(full_name)
    if is_dup:
        return jsonify({"valid": True, "duplicate": True, "message": dup_msg})

    return jsonify({"valid": True, "duplicate": False, "message": "Name is available."})


@students_bp.route("/admin/enroll/create", methods=["POST"])
@login_required
def create_student():
    """
    Step 1: Validate identity information and initialize an enrollment staging session.
    DO NOT insert into database yet — student is ONLY enrolled after successfully
    capturing all 20 quality-verified images.
    Supports Students/Employees and Guests/Visitors (no ID required for guests).
    """
    first_name = request.form.get("first_name", "").strip()
    last_name = request.form.get("last_name", "").strip()
    full_name = request.form.get("full_name", "").strip()

    if not full_name and (first_name or last_name):
        full_name = f"{first_name} {last_name}".strip()

    student_id = request.form.get("student_id", "").strip()
    program = request.form.get("program", "").strip()
    user_type = request.form.get("user_type", "student").strip().lower()

    if not full_name:
        return jsonify({"success": False, "message": "First Name and Last Name are required."}), 400

    # Clean whitespace
    full_name = " ".join(full_name.split())

    # Proper name validation
    name_regex = re.compile(r"^[A-Za-zÀ-ÿñÑ\s\.\-']+$")
    if not name_regex.match(full_name):
        return jsonify({
            "success": False,
            "message": "Invalid name format. Names must only contain letters, spaces, hyphens, and apostrophes (no numbers or special symbols)."
        }), 400

    if len(full_name) < 2:
        return jsonify({"success": False, "message": "Name is too short (minimum 2 characters)."}), 400

    if first_name and not name_regex.match(first_name):
        return jsonify({"success": False, "message": "First Name contains invalid characters. Numbers and special symbols are not allowed."}), 400

    if last_name and not name_regex.match(last_name):
        return jsonify({"success": False, "message": "Last Name contains invalid characters. Numbers and special symbols are not allowed."}), 400

    # Automatically format name with proper capitalization if entered in lowercase
    if not any(c.isupper() for c in full_name):
        full_name = full_name.title()

    is_guest = (user_type == "guest") or (program.lower() in ["guest", "guest / visitor", "visiting-researcher", "community-user"])

    if is_guest:
        if not program:
            program = "Guest"
        # Auto-generate unique guest ID if not provided
        if not student_id:
            student_id = db.generate_guest_id()
    else:
        if not student_id:
            return jsonify({
                "success": False,
                "message": "Student / Employee ID is required. (Select 'Guest / Visitor' if no ID is required.)"
            }), 400
        if len(student_id) > 10:
            return jsonify({
                "success": False,
                "message": "Student / Employee ID cannot exceed 10 characters."
            }), 400
        if not program:
            return jsonify({"success": False, "message": "Program / Department is required."}), 400

    student_id = student_id.strip()
    if student_id and not student_id.startswith("GST-") and len(student_id) > 10:
        return jsonify({
            "success": False,
            "message": "ID number cannot exceed 10 characters."
        }), 400

    # Strict duplicate verification against database (case-insensitive and trimmed)
    is_duplicate, dup_msg = db.check_student_duplicate(full_name, student_id, is_guest=is_guest)
    if is_duplicate:
        return jsonify({"success": False, "message": dup_msg}), 409

    # Generate a temporary staging session token
    # No student row is created in SQLite yet!
    enroll_token = f"stage_{int(time.time())}_{uuid.uuid4().hex[:8]}"
    stage_dir = os.path.join(Config.FACE_DATA_DIR, "staging", enroll_token)
    os.makedirs(stage_dir, exist_ok=True)

    # Store staging metadata
    meta_path = os.path.join(stage_dir, "meta.json")
    with open(meta_path, "w", encoding="utf-8") as f:
        json.dump({
            "full_name": full_name,
            "student_id": student_id,
            "program": program,
            "is_guest": is_guest,
            "created_at": time.time(),
        }, f)

    return jsonify({
        "success": True,
        "enroll_token": enroll_token,
        "student_db_id": enroll_token,  # compatibility alias
        "full_name": full_name,
        "student_id": student_id,
        "program": program,
        "is_guest": is_guest,
    })


@students_bp.route("/admin/enroll/capture", methods=["POST"])
@login_required
def capture_face():
    """
    Step 2: Receive a base64-encoded JPEG frame into the staging directory.
    Strictly validates: single face, blur, lighting, dimensions, and motion difference.
    Does NOT affect permanent database records.
    """
    data = request.get_json() or {}
    token = data.get("enroll_token") or data.get("token") or data.get("student_db_id")
    image_data = data.get("image")  # base64 data URL: "data:image/jpeg;base64,..."
    img_index = int(data.get("img_index", 0))

    if not image_data or not token:
        return jsonify({"success": False, "message": "Missing required data."}), 400

    # Locate staging directory
    stage_dir = os.path.join(Config.FACE_DATA_DIR, "staging", str(token))
    if not os.path.exists(stage_dir):
        return jsonify({
            "success": False,
            "message": "Enrollment session expired or not found. Please restart from Step 1.",
        }), 400

    # If restarting capture at index 0, clean out previously captured frames in staging
    if img_index == 0:
        for f in os.listdir(stage_dir):
            if f.startswith("img_") and f.endswith(".jpg"):
                try:
                    os.remove(os.path.join(stage_dir, f))
                except Exception:
                    pass

    # Decode base64 image
    try:
        header, encoded = image_data.split(",", 1)
        img_bytes = base64.b64decode(encoded)
        np_arr = np.frombuffer(img_bytes, np.uint8)
        frame = cv2.imdecode(np_arr, cv2.IMREAD_COLOR)
        if frame is None:
            return jsonify({"success": False, "message": "Invalid image payload."}), 400
    except Exception as e:
        return jsonify({"success": False, "message": f"Failed to decode image: {e}"}), 400

    detector = FaceDetector()
    faces, gray = detector.detect(frame)

    # 1. Reject if no face detected
    if len(faces) == 0:
        return jsonify({
            "success": False,
            "message": "No face detected in frame. Please face the camera directly.",
            "error_type": "no_face",
        })

    # 2. Reject if multiple faces detected
    if len(faces) > 1:
        return jsonify({
            "success": False,
            "message": f"Multiple faces detected ({len(faces)}). Only the enrolling person should be visible.",
            "error_type": "multiple_faces",
        })

    face_bbox = faces[0]

    # 3. Quality audit: blur, lighting, dimensions
    is_valid, quality_reason, metrics = detector.validate_face_quality(frame, face_bbox)
    if not is_valid:
        return jsonify({
            "success": False,
            "message": quality_reason,
            "error_type": "quality_failure",
            "metrics": metrics,
        })

    # 4. Standardized Preprocessing
    x, y, w, h = face_bbox
    h_img, w_img = frame.shape[:2]
    x1, y1 = max(0, x), max(0, y)
    x2, y2 = min(w_img, x + w), min(h_img, y + h)
    face_bgr_roi = frame[y1:y2, x1:x2]

    # 5. Check frame difference against previous captured image in staging
    if img_index > 0:
        prev_img_path = os.path.join(stage_dir, f"img_{img_index - 1:03d}.jpg")
        if os.path.exists(prev_img_path):
            prev_face = cv2.imread(prev_img_path)
            diff_score = FaceDetector.calculate_frame_difference(face_bgr_roi, prev_face)
            if diff_score < Config.ENROLLMENT_FRAME_DIFF_THRESHOLD:
                return jsonify({
                    "success": False,
                    "message": "Face position too similar to previous frame. Please move slightly or adjust expression.",
                    "error_type": "duplicate_frame",
                    "diff_score": round(diff_score, 2),
                })

    # Save standardized 200x200 BGR face image in staging folder
    face_roi_resized = cv2.resize(face_bgr_roi, (200, 200))
    img_path = os.path.join(stage_dir, f"img_{img_index:03d}.jpg")
    cv2.imwrite(img_path, face_roi_resized)

    # 6. Pose guidance distribution (20 images total):
    # 0..4 (1-5): Frontal
    # 5..9 (6-10): Slight head turns
    # 10..14 (11-15): Expressions
    # 15..19 (16-20): Lighting / distance variation
    next_idx = img_index + 1
    if next_idx < 5:
        phase = 1
        guidance = "Phase 1/4: Look straight at camera with neutral expression."
    elif next_idx < 10:
        phase = 2
        guidance = "Phase 2/4: Turn head slightly to the left or right."
    elif next_idx < 15:
        phase = 3
        guidance = "Phase 3/4: Show modest expression variations (slight smile, blink)."
    elif next_idx < 20:
        phase = 4
        guidance = "Phase 4/4: Slight distance, tilt, or lighting variation."
    else:
        phase = 4
        guidance = "All 20 images captured! Proceeding to finalize enrollment…"

    return jsonify({
        "success": True,
        "saved_path": img_path,
        "img_index": img_index,
        "next_index": next_idx,
        "phase": phase,
        "guidance": guidance,
        "metrics": metrics,
    })


@students_bp.route("/admin/enroll/train", methods=["POST"])
@login_required
def trigger_training():
    """
    Step 3: Finalize Enrollment.
    Verifies that all 20 quality-checked images were captured.
    Re-checks for duplicates, inserts the student record into the database,
    moves staging images to the permanent face_data/<student_id> folder,
    and trains the recognition models.
    """
    data = request.get_json() or {}
    token = (
        data.get("enroll_token")
        or data.get("token")
        or data.get("student_db_id")
        or request.form.get("token")
    )

    if not token:
        # Fallback: simple retrain without a pending staging enrollment
        result = train_model()
        return jsonify(result)

    stage_dir = os.path.join(Config.FACE_DATA_DIR, "staging", str(token))
    if not os.path.exists(stage_dir):
        return jsonify({
            "success": False,
            "message": "Enrollment session not found or already completed.",
        }), 400

    meta_file = os.path.join(stage_dir, "meta.json")
    if not os.path.exists(meta_file):
        return jsonify({"success": False, "message": "Enrollment metadata missing."}), 400

    with open(meta_file, "r", encoding="utf-8") as f:
        meta = json.load(f)

    full_name = meta.get("full_name", "").strip()
    student_id = meta.get("student_id", "").strip()
    program = meta.get("program", "").strip()
    is_guest = meta.get("is_guest", False) or (program.lower() in ["guest", "guest / visitor", "visiting-researcher", "community-user"])

    # 1. Verify that all 20 images have been captured
    captured_files = sorted([
        f for f in os.listdir(stage_dir)
        if f.startswith("img_") and f.endswith(".jpg")
    ])
    required_count = Config.ENROLLMENT_IMAGE_COUNT

    if len(captured_files) < required_count:
        return jsonify({
            "success": False,
            "message": (
                f"Cannot enroll user: only {len(captured_files)} of {required_count} images were captured. "
                f"All 20 quality-verified images must be completed before enrollment is finalized."
            ),
        }), 400

    # 2. Strict concurrency duplicate check
    is_dup, dup_msg = db.check_student_duplicate(full_name, student_id, is_guest=is_guest)
    if is_dup:
        shutil.rmtree(stage_dir, ignore_errors=True)
        return jsonify({"success": False, "message": dup_msg}), 409

    # 3. ONLY NOW insert the student into SQLite!
    new_student_db_id = db.create_student(full_name, student_id, program)

    # 4. Move captured images from staging to permanent face_data/<registered_name>
    safe_name = sanitize_name_for_filesystem(full_name)
    permanent_dir = os.path.join(Config.FACE_DATA_DIR, safe_name)
    os.makedirs(permanent_dir, exist_ok=True)

    for idx, f in enumerate(captured_files):
        src = os.path.join(stage_dir, f)
        dest_filename = f"{safe_name}_{idx:03d}.jpg"
        dst = os.path.join(permanent_dir, dest_filename)
        shutil.copy2(src, dst)

    # 5. Clean up staging directory
    shutil.rmtree(stage_dir, ignore_errors=True)

    # 6. Retrain active models
    train_result = train_model()

    user_label = "Guest" if is_guest else "Student"
    return jsonify({
        "success": True,
        "student_db_id": new_student_db_id,
        "full_name": full_name,
        "student_id": student_id,
        "program": program,
        "is_guest": is_guest,
        "num_images": len(captured_files),
        "num_subjects": train_result.get("num_subjects", 1),
        "message": f"{user_label} '{full_name}' ({student_id}) successfully enrolled and model trained!",
    })


@students_bp.route("/admin/enroll/cancel", methods=["POST"])
@login_required
def cancel_enrollment():
    """Cancel enrollment session and purge temporary staging images."""
    data = request.get_json() or {}
    token = data.get("enroll_token") or data.get("token")
    if token:
        stage_dir = os.path.join(Config.FACE_DATA_DIR, "staging", str(token))
        if os.path.exists(stage_dir):
            shutil.rmtree(stage_dir, ignore_errors=True)
    return jsonify({"success": True})
