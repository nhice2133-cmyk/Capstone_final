"""
SMART ENTRY — Kiosk & Recognition Routes

Endpoints:
  GET  /kiosk            — full-screen kiosk interface (Entry camera)
  GET  /kiosk/exit       — passive exit kiosk page
  GET  /kiosk/stream     — MJPEG video stream (Entry camera)
  GET  /kiosk/exit_stream — MJPEG video stream (Exit camera)
  POST /kiosk/recognize  — run recognition on a single base64 frame
  POST /kiosk/log_entry  — log Time In + visit purpose after recognition
  POST /kiosk/log_exit   — log Time Out (exit camera)

  GET  /admin/alerts     — security alerts list page
  POST /admin/alerts/resolve/<id> — mark alert resolved
"""
import os
import cv2
import base64
import numpy as np
from datetime import datetime, timedelta
from flask import (Blueprint, render_template, request, jsonify,
                   redirect, url_for, flash, Response)
from flask_login import login_required
from database import database as db
from recognition.face_detection import FaceDetector
from recognition.face_recognition import FaceRecognizer
from config import Config, BASE_DIR

kiosk_bp = Blueprint("kiosk", __name__)

# Module-level singletons (loaded once at startup)
_detector = None
_recognizer = None

# Simple cooldown tracker for stranger alerts  {camera_label: last_alert_time}
_last_alert_time: dict = {}
_last_unknown_face: dict = {}
_last_recognized_time: dict = {}  # {(student_db_id, camera_label): timestamp}


def _get_detector():
    global _detector
    if _detector is None:
        _detector = FaceDetector()
    return _detector


def _get_recognizer():
    global _recognizer
    if _recognizer is None:
        _recognizer = FaceRecognizer()
    return _recognizer


def _reload_recognizer():
    global _recognizer
    _recognizer = FaceRecognizer()


# ── Kiosk Pages ───────────────────────────────────────────────────────────────

@kiosk_bp.route("/kiosk")
def kiosk_entry():
    """Full-screen interactive entry kiosk."""
    return render_template("kiosk/kiosk.html", mode="entry")


@kiosk_bp.route("/kiosk/exit")
def kiosk_exit():
    """Redirect exit requests to the entry kiosk (entry-only deployment)."""
    return redirect(url_for("kiosk.kiosk_entry"))


# ── MJPEG Streams (optional — for display-only feed) ─────────────────────────

def _generate_stream(camera_index: int):
    """Yield MJPEG frames from a USB webcam."""
    cap = cv2.VideoCapture(camera_index, cv2.CAP_DSHOW)
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, Config.FRAME_WIDTH)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, Config.FRAME_HEIGHT)
    detector = _get_detector()
    recognizer = _get_recognizer()

    while cap.isOpened():
        ret, frame = cap.read()
        if not ret:
            break
        faces, gray = detector.detect(frame)
        color = (0, 200, 100)
        for face in faces:
            face_roi = detector.crop_face(gray, face)
            label, score, student_info = recognizer.predict(face_roi)
            if student_info:
                name = student_info["full_name"]
                color = (0, 200, 100)
                x, y, w, h = face
                cv2.putText(frame, name, (x, y - 10),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.7, color, 2)
            else:
                color = (0, 0, 220)
        detector.draw_rectangles(frame, faces, color=color)

        _, buffer = cv2.imencode(".jpg", frame)
        yield (b"--frame\r\nContent-Type: image/jpeg\r\n\r\n"
               + buffer.tobytes() + b"\r\n")

    cap.release()


@kiosk_bp.route("/kiosk/stream")
def entry_stream():
    return Response(_generate_stream(Config.ENTRY_CAMERA_INDEX),
                    mimetype="multipart/x-mixed-replace; boundary=frame")


@kiosk_bp.route("/kiosk/exit_stream")
def exit_stream():
    return Response(_generate_stream(Config.EXIT_CAMERA_INDEX),
                    mimetype="multipart/x-mixed-replace; boundary=frame")


# ── Recognition API ───────────────────────────────────────────────────────────

@kiosk_bp.route("/kiosk/recognize", methods=["POST"])
def recognize():
    """
    Accepts a base64 image frame, runs Haar Cascade + SFace Deep Face Recognizer, returns:
    - recognized student info, or
    - "unknown" with alert logging if stranger detected.
    Safe decision logic:
    1. Detect face and apply consistent preprocessing
    2. Check threshold
    3. Resolve label mapping and verify active status
    4. Enforce cooldown to prevent duplicate logging loops
    """
    data = request.get_json()
    image_data = data.get("image")
    camera_label = data.get("camera", "entry")  # "entry" or "exit"

    if not image_data:
        return jsonify({"status": "error", "message": "No image data."}), 400

    # Decode base64
    try:
        header, encoded = image_data.split(",", 1)
        img_bytes = base64.b64decode(encoded)
        np_arr = np.frombuffer(img_bytes, np.uint8)
        frame = cv2.imdecode(np_arr, cv2.IMREAD_COLOR)
        if frame is None:
            return jsonify({"status": "error", "message": "Corrupted image frame."}), 400
    except Exception as e:
        return jsonify({"status": "error", "message": f"Decode error: {e}"}), 400

    detector = _get_detector()
    recognizer = _get_recognizer()

    faces, gray = detector.detect(frame, min_size=(50, 50))
    if not faces:
        return jsonify({"status": "no_face"})

    # Process the largest face only
    largest = max(faces, key=lambda f: f[2] * f[3])

    # Build face_box relative to frame dimensions so frontend can scale it
    frame_h, frame_w = frame.shape[:2]
    fx, fy, fw, fh = int(largest[0]), int(largest[1]), int(largest[2]), int(largest[3])
    face_box = {
        "x": fx / frame_w,
        "y": fy / frame_h,
        "w": fw / frame_w,
        "h": fh / frame_h,
    }

    # Extract natural color face crop for high-accuracy recognition (no premature CLAHE)
    face_roi = detector.crop_face(frame, largest, apply_preprocessing=False)
    try:
        label, score, student_info = recognizer.predict(face_roi)
    except Exception as e:
        print(f"[RECOGNITION ERROR] {e}")
        return jsonify({
            "status": "error",
            "message": str(e),
            "face_box": face_box,
        })

    # ── Safe Recognition Verification ─────────────────────────────────────────
    if student_info is not None and student_info.get("status") == "active":
        student_db_id = student_info["student_db_id"]
        now = datetime.now()
        last_rec = _last_recognized_time.get((student_db_id, camera_label))
        
        # If recognized recently on this camera, ignore to prevent UI looping
        if last_rec and (now - last_rec).total_seconds() < Config.RECOGNITION_COOLDOWN_SECONDS:
            return jsonify({"status": "cooldown", "face_box": face_box})

        _last_recognized_time[(student_db_id, camera_label)] = now
        
        return jsonify({
            "status": "recognized",
            "student_db_id": student_db_id,
            "full_name": student_info["full_name"],
            "student_id": student_info["student_id"],
            "program": student_info["program"],
            "confidence": round(float(score), 2),
            "model_type": recognizer.active_model,
            "face_box": face_box,
        })

    # ── Stranger / Unknown detected ───────────────────────────────────────────
    now = datetime.now()
    last = _last_alert_time.get(camera_label)
    last_face = _last_unknown_face.get(camera_label)
    
    is_new_person = True
    current_face_gray = cv2.cvtColor(face_roi, cv2.COLOR_BGR2GRAY) if len(face_roi.shape) == 3 else face_roi
    current_face_resized = cv2.resize(current_face_gray, (100, 100))
    
    if last_face is not None:
        err = np.sum((current_face_resized.astype("float") - last_face.astype("float")) ** 2)
        err /= float(current_face_resized.shape[0] * current_face_resized.shape[1])
        if err < 3000:
            is_new_person = False

    # Log alert if it's a new person OR if it's been more than 60 seconds since the last alert
    if is_new_person or last is None or (now - last).total_seconds() > 60:
        _last_alert_time[camera_label] = now
        _last_unknown_face[camera_label] = current_face_resized
        # Save snapshot
        snapshot_filename = f"alert_{now.strftime('%Y%m%d_%H%M%S')}_{camera_label}.jpg"
        os.makedirs(Config.ALERTS_SNAPSHOT_DIR, exist_ok=True)
        snapshot_path = os.path.join(Config.ALERTS_SNAPSHOT_DIR, snapshot_filename)
        cv2.imwrite(snapshot_path, frame)
        db.log_alert(
            snapshot_path=f"snapshots/{snapshot_filename}",
            confidence_score=round(float(score), 2),
        )

    return jsonify({
        "status": "unknown",
        "confidence": round(float(score), 2),
        "model_type": recognizer.active_model,
        "face_box": face_box,
    })


# ── Attendance Logging ────────────────────────────────────────────────────────

@kiosk_bp.route("/kiosk/log_entry", methods=["POST"])
def log_entry():
    """Log Time In + visit purpose for the entry kiosk."""
    data = request.get_json()
    student_db_id = data.get("student_db_id")
    visit_purpose = data.get("visit_purpose", "General Space")

    if not student_db_id:
        return jsonify({"success": False, "message": "No student_db_id provided."}), 400

    # Cross-verify student exists and is active before logging
    student = db.get_student_by_db_id(student_db_id)
    if not student or student["status"] != "active":
        return jsonify({"success": False, "message": "Unauthorized: Student is inactive or does not exist."}), 403

    record_id = db.log_time_in(student_db_id, visit_purpose, node="entry")
    return jsonify({"success": True, "record_id": record_id})


@kiosk_bp.route("/kiosk/log_exit", methods=["POST"])
def log_exit():
    """Log Time Out for the exit camera."""
    data = request.get_json()
    student_db_id = data.get("student_db_id")

    if not student_db_id:
        return jsonify({"success": False, "message": "No student_db_id provided."}), 400

    # Cross-verify student exists and is active before logging
    student = db.get_student_by_db_id(student_db_id)
    if not student or student["status"] != "active":
        return jsonify({"success": False, "message": "Unauthorized: Student is inactive or does not exist."}), 403

    active_session = db.get_active_inside_session(student_db_id)
    if not active_session:
        return jsonify({
            "success": False,
            "error_type": "not_entered",
            "message": "Please go to the entrance",
        }), 200

    updated = db.log_time_out(student_db_id)
    return jsonify({
        "success": updated,
        "error_type": None if updated else "not_entered",
        "message": "Time out recorded successfully." if updated else "Please go to the entrance",
    })


# ── Security Alerts (Admin) ───────────────────────────────────────────────────

@kiosk_bp.route("/admin/alerts")
@login_required
def alerts_page():
    alerts = db.get_alerts(resolved=0, limit=200)
    return render_template("admin/alerts.html", alerts=alerts, active_tab="active")


@kiosk_bp.route("/admin/alerts/resolved")
@login_required
def resolved_alerts_page():
    alerts = db.get_alerts(resolved=1, limit=200)
    return render_template("admin/alerts.html", alerts=alerts, active_tab="resolved")


@kiosk_bp.route("/admin/alerts/resolve/<int:alert_id>", methods=["POST"])
@login_required
def resolve_alert(alert_id):
    db.resolve_alert(alert_id)
    flash("Alert marked as resolved.", "success")
    return redirect(url_for("kiosk.alerts_page"))


@kiosk_bp.route("/admin/alerts/resolve_all", methods=["POST"])
@login_required
def resolve_all_alerts():
    db.resolve_all_alerts()
    flash("All active alerts have been marked as resolved.", "success")
    return redirect(url_for("kiosk.alerts_page"))


@kiosk_bp.route("/admin/alerts/delete/<int:alert_id>", methods=["POST"])
@login_required
def delete_alert(alert_id):
    snapshot = db.delete_alert(alert_id)
    if snapshot:
        path = os.path.join(BASE_DIR, "static", snapshot)
        if os.path.exists(path):
            os.remove(path)
    flash("Alert deleted.", "success")
    return redirect(url_for("kiosk.resolved_alerts_page"))


@kiosk_bp.route("/admin/alerts/delete_all_resolved", methods=["POST"])
@login_required
def delete_all_resolved_alerts():
    snapshots = db.delete_all_resolved_alerts()
    for snapshot in snapshots:
        path = os.path.join(BASE_DIR, "static", snapshot)
        if os.path.exists(path):
            os.remove(path)
    flash("All resolved alerts have been deleted.", "success")
    return redirect(url_for("kiosk.resolved_alerts_page"))


# ── Utility: reload recognizer after training or model switch ──────────────────

@kiosk_bp.route("/kiosk/reload_model", methods=["POST"])
def reload_model():
    """Hot-reloads the active model and label mapping in memory."""
    _reload_recognizer()
    return jsonify({"success": True, "message": "Model reloaded."})
