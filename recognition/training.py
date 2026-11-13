"""
SMART ENTRY — SFace Deep Feature Training & Embeddings Module
Extracts 128-dimensional facial feature embeddings for all ACTIVE students,
computes normalized centroid representation vectors,
and updates metadata for the pure SFace deep learning architecture.
"""
import os
import cv2
import numpy as np
from datetime import datetime
from config import Config, sanitize_name_for_filesystem
from database import database as db
from recognition.model_manager import ModelManager
from recognition.sface_recognizer import SFaceRecognizer


def train_model() -> dict:
    """
    Scans enrolled students in the database, extracts SFace 128-D deep feature
    embeddings, computes centroid vectors, and updates versioned metadata.

    Returns
    -------
    result : dict
        {
            'success': bool,
            'message': str,
            'num_subjects': int,
            'num_images': int,
            'version': str
        }
    """
    face_data_dir = Config.FACE_DATA_DIR
    if not os.path.exists(face_data_dir):
        return {
            "success": False,
            "message": "face_data/ directory not found.",
            "num_subjects": 0,
            "num_images": 0,
        }

    # 1. Query active students
    all_students = db.get_all_students()
    active_students = [s for s in all_students if s["status"] == "active"]

    if not active_students:
        # Cleanly reset embeddings and metadata when 0 active students remain
        try:
            sface = SFaceRecognizer()
            if sface.is_available:
                sface._embeddings_db = {}
                sface._centroids = {}
                sface.save_embeddings()
        except Exception:
            pass

        version_str = f"v{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        meta = ModelManager.get_metadata()
        meta["version"] = version_str
        meta["num_students"] = 0
        meta["num_images"] = 0
        meta["label_map"] = {}
        ModelManager.save_metadata(meta)

        return {
            "success": True,
            "message": "All students removed. Model reset to 0 enrolled students.",
            "num_subjects": 0,
            "num_images": 0,
            "version": version_str,
        }

    # 2. Initialize SFace Recognizer and extract embeddings
    sface = SFaceRecognizer()
    if not sface.is_available:
        return {
            "success": False,
            "message": "OpenCV SFace deep neural network model could not be loaded from disk.",
            "num_subjects": 0,
            "num_images": 0,
        }

    sync_result = sface.update_all_embeddings()
    if not sync_result.get("success"):
        return {
            "success": False,
            "message": sync_result.get("message", "Failed to extract facial embeddings."),
            "num_subjects": 0,
            "num_images": 0,
        }

    enrolled_count = sync_result.get("processed_students", 0)
    total_images = sync_result.get("total_vectors", 0)

    if enrolled_count == 0 or total_images == 0:
        return {
            "success": False,
            "message": "No valid face images found for active students.",
            "num_subjects": 0,
            "num_images": 0,
        }

    # 4. Generate decoupled label map for fast direct lookup
    label_map = {}
    for idx, student in enumerate(active_students):
        s_dict = dict(student)
        label_map[str(student["id"])] = {
            "student_db_id": student["id"],
            "student_id": student["student_id"],
            "full_name": student["full_name"],
            "program": s_dict.get("program", "BSIT"),
            "status": "active"
        }

    # 4. Update Model Metadata
    version_str = f"v{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    meta = ModelManager.get_metadata()
    meta["active_model"] = "sface"
    meta["version"] = version_str
    meta["num_students"] = enrolled_count
    meta["num_images"] = total_images
    meta["label_map"] = label_map
    ModelManager.save_metadata(meta)

    return {
        "success": True,
        "message": (
            f"SFace deep feature embeddings generated successfully ({version_str}): "
            f"{total_images} feature vectors across {enrolled_count} active student(s)."
        ),
        "num_subjects": enrolled_count,
        "num_images": total_images,
        "version": version_str,
    }


def get_training_stats() -> dict:
    """Return comprehensive stats about available models and training data."""
    meta = ModelManager.get_metadata()
    face_data_dir = Config.FACE_DATA_DIR

    active_students = [s for s in db.get_all_students() if s["status"] == "active"]
    disk_images = 0
    students_with_images = 0

    if os.path.exists(face_data_dir):
        for s in active_students:
            safe_name = sanitize_name_for_filesystem(s["full_name"])
            named_folder = os.path.join(face_data_dir, safe_name)
            legacy_folder = os.path.join(face_data_dir, str(s["id"]))
            s_folder = named_folder if os.path.isdir(named_folder) else legacy_folder
            if os.path.isdir(s_folder):
                imgs = [f for f in os.listdir(s_folder) if f.lower().endswith((".enc", ".jpg", ".png", ".jpeg"))]
                if imgs:
                    students_with_images += 1
                    disk_images += len(imgs)

    sface_ready = (
        os.path.exists(Config.SFACE_MODEL_PATH)
        and os.path.exists(Config.YUNET_MODEL_PATH)
        and os.path.exists(Config.SFACE_EMBEDDINGS_PATH)
    )

    return {
        "active_model": "sface",
        "version": meta.get("version", "1.0.0"),
        "updated_at": meta.get("updated_at", "N/A"),
        "num_active_students": len(active_students),
        "students_with_images": students_with_images,
        "total_images": disk_images,
        "sface_threshold": meta.get("sface_threshold", Config.SFACE_THRESHOLD),
        "sface_model_exists": sface_ready,
        "last_evaluation": meta.get("last_evaluation"),
    }
