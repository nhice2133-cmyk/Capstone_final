"""
SMART ENTRY — Configuration
Centralizes all configurable parameters for the application.
"""
import os
import re

BASE_DIR = os.path.abspath(os.path.dirname(__file__))


def sanitize_name_for_filesystem(name: str) -> str:
    r"""
    Sanitize a registered person's name for safe filesystem directory and file naming.
    Removes characters prohibited by filesystems: \ / : * ? " < > |
    """
    if not name:
        return "unnamed_user"
    cleaned = re.sub(r'[\\/*?:"<>|]', '', str(name)).strip()
    return cleaned if cleaned else "unnamed_user"


class Config:
    BASE_DIR = BASE_DIR
    # ── Flask ──────────────────────────────────────────────────────────────
    SECRET_KEY = os.environ.get("SECRET_KEY", "smart_entry_secret_2026_csucc")
    DEBUG = os.environ.get("DEBUG", "True").lower() == "true"

    # ── Administrator Offline Recovery ─────────────────────────────────────
    ADMIN_RECOVERY_KEY = os.environ.get("ADMIN_RECOVERY_KEY", "CSUCC-ATHENAEUM-RESET-2026")
    DEFAULT_SECURITY_QUESTION = "What is the official name of the CSUCC library building?"
    DEFAULT_SECURITY_ANSWER = "Athenaeum"

    # ── Database ───────────────────────────────────────────────────────────
    DATABASE_PATH = os.path.join(BASE_DIR, "database", "smart_entry.db")

    # ── Face Recognition & Models ──────────────────────────────────────────
    MODELS_DIR = os.path.join(BASE_DIR, "recognition", "models")
    MODEL_HISTORY_DIR = os.path.join(BASE_DIR, "recognition", "models", "history")

    # Haar Cascade classifier XML
    HAAR_CASCADE_PATH = os.path.join(
        BASE_DIR, "recognition", "haarcascade", "haarcascade_frontalface_default.xml"
    )

    # Active model type: "sface" (OpenCV Deep Feature Embeddings)
    ACTIVE_MODEL_TYPE = "sface"

    # SFace / YuNet ONNX Deep Learning Models & Embeddings
    SFACE_MODEL_PATH = os.path.join(MODELS_DIR, "face_recognition_sface_2021dec.onnx")
    YUNET_MODEL_PATH = os.path.join(MODELS_DIR, "face_detection_yunet_2023mar.onnx")
    SFACE_EMBEDDINGS_PATH = os.path.join(MODELS_DIR, "sface_embeddings.npz")
    MODEL_METADATA_PATH = os.path.join(MODELS_DIR, "model_metadata.json")
    LABEL_MAP_PATH = os.path.join(MODELS_DIR, "label_map.json")

    # SFace Calibrated Cosine Similarity Threshold (higher = closer match; accepts >= threshold)
    SFACE_THRESHOLD = 0.363
    RECOGNITION_THRESHOLD = 0.363

    # Images to capture per user during enrollment
    ENROLLMENT_IMAGE_COUNT = 20

    # Face Quality & Diversity Thresholds for Enrollment
    ENROLLMENT_MIN_FACE_SIZE = (80, 80)
    ENROLLMENT_BLUR_THRESHOLD = 45.0       # Laplacian variance (below this is blurry)
    ENROLLMENT_MIN_BRIGHTNESS = 40.0       # Mean pixel value (below this is underexposed)
    ENROLLMENT_MAX_BRIGHTNESS = 220.0      # Mean pixel value (above this is overexposed)
    ENROLLMENT_FRAME_DIFF_THRESHOLD = 12.0 # Minimum MSE difference to prevent identical burst frames

    # Face images storage (one sub-folder per registered user name)
    FACE_DATA_DIR = os.path.join(BASE_DIR, "face_data")

    # Stranger alert snapshots
    ALERTS_SNAPSHOT_DIR = os.path.join(BASE_DIR, "static", "snapshots")

    # ── Camera ─────────────────────────────────────────────────────────────
    # Entry webcam index (usually 0 for the first USB webcam)
    ENTRY_CAMERA_INDEX = 0
    # Exit webcam index (usually 1 for the second USB webcam)
    EXIT_CAMERA_INDEX = 1

    # Frame resolution for face detection pipeline
    FRAME_WIDTH = 640
    FRAME_HEIGHT = 480

    # ── Detection Cooldowns ────────────────────────────────────────────────
    # Seconds to wait before a new alert is logged for the same unknown face
    ALERT_COOLDOWN_SECONDS = 10

    # Seconds to wait before recognizing the SAME student again on the SAME camera
    RECOGNITION_COOLDOWN_SECONDS = 60

    # ── Session ────────────────────────────────────────────────────────────
    # Minutes of inactivity before admin session expires
    SESSION_TIMEOUT_MINUTES = 30
