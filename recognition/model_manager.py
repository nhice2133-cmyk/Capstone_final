"""
SMART ENTRY — Model Manager Module (SFace Deep Learning Architecture)
Handles versioning, label mapping, model metadata, atomic updates,
and administrator threshold configuration for OpenCV SFace deep embeddings.
"""
import os
import json
import shutil
from datetime import datetime
from config import Config
from database import database as db


class ModelManager:
    """
    Central authority for SFace deep recognition models, versioning,
    student metadata mapping, and similarity threshold calibration.
    """

    @classmethod
    def get_metadata(cls) -> dict:
        """Load current model metadata from disk, or initialize defaults."""
        os.makedirs(Config.MODELS_DIR, exist_ok=True)
        if os.path.exists(Config.MODEL_METADATA_PATH):
            try:
                with open(Config.MODEL_METADATA_PATH, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    data["active_model"] = "sface"
                    return data
            except Exception:
                pass

        default_meta = {
            "active_model": "sface",
            "version": "1.0.0",
            "updated_at": datetime.now().isoformat(),
            "sface_threshold": Config.SFACE_THRESHOLD,
            "num_students": 0,
            "num_images": 0,
            "label_map": {},
            "last_evaluation": None,
        }
        cls.save_metadata(default_meta)
        return default_meta

    @classmethod
    def save_metadata(cls, meta: dict):
        """Atomically persist metadata and label map to disk."""
        os.makedirs(Config.MODELS_DIR, exist_ok=True)
        meta["updated_at"] = datetime.now().isoformat()
        meta["active_model"] = "sface"
        
        temp_meta = Config.MODEL_METADATA_PATH + ".tmp"
        with open(temp_meta, "w", encoding="utf-8") as f:
            json.dump(meta, f, indent=2)
        shutil.move(temp_meta, Config.MODEL_METADATA_PATH)

        label_map = meta.get("label_map", {})
        temp_map = Config.LABEL_MAP_PATH + ".tmp"
        with open(temp_map, "w", encoding="utf-8") as f:
            json.dump(label_map, f, indent=2)
        shutil.move(temp_map, Config.LABEL_MAP_PATH)

    @classmethod
    def get_active_model_type(cls) -> str:
        """Always returns 'sface'."""
        return "sface"

    @classmethod
    def set_active_model_type(cls, model_type: str = "sface") -> bool:
        """Confirms 'sface' as active engine."""
        meta = cls.get_metadata()
        meta["active_model"] = "sface"
        cls.save_metadata(meta)
        return True

    @classmethod
    def get_threshold(cls, model_type: str = "sface") -> float:
        """Get calibrated SFace cosine similarity threshold."""
        meta = cls.get_metadata()
        return float(meta.get("sface_threshold", Config.SFACE_THRESHOLD))

    @classmethod
    def set_threshold(cls, model_type: str, threshold: float) -> bool:
        """Update and persist calibrated SFace cosine similarity threshold."""
        meta = cls.get_metadata()
        meta["sface_threshold"] = float(threshold)
        cls.save_metadata(meta)
        return True

    @classmethod
    def resolve_label(cls, label_id: int) -> dict | None:
        """Resolve student DB id to student metadata dictionary."""
        return cls.resolve_student_id(label_id)

    @classmethod
    def resolve_student_id(cls, student_db_id: int) -> dict | None:
        """Resolve student database ID to active student record."""
        student = db.get_student_by_db_id(student_db_id)
        if not student or student["status"] != "active":
            return None

        s_dict = dict(student)
        return {
            "student_db_id": s_dict["id"],
            "student_id": s_dict["student_id"],
            "full_name": s_dict["full_name"],
            "program": s_dict.get("program", "BSIT"),
            "year_level": s_dict.get("year_level", "N/A"),
            "role": s_dict.get("role", "Student"),
            "status": s_dict.get("status", "active"),
        }
