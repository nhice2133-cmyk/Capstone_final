"""
SMART ENTRY — OpenCV SFace Deep Face Recognition Module
Utilizes OpenCV's native SFace ONNX deep neural network (128-D embeddings)
with YuNet face detection and alignment for high-accuracy verification.
"""
import os
import cv2
import json
import numpy as np
from config import Config, sanitize_name_for_filesystem
from database import database as db
from recognition.model_manager import ModelManager


class SFaceRecognizer:
    """
    Deep learning face recognizer utilizing OpenCV's pretrained SFace model.
    Runs entirely on CPU in pure OpenCV with zero heavy third-party dependencies.
    """

    def __init__(self):
        self._sface = None
        self._yunet = None
        self._embeddings_db = {}  # student_db_id -> list of (1, 128) embeddings
        self._centroids = {}      # student_db_id -> (1, 128) centroid embedding
        self._is_loaded = False

        self._init_models()
        self.load_embeddings()

    def _init_models(self):
        """Initialize SFace and YuNet if models are present on disk."""
        if os.path.exists(Config.SFACE_MODEL_PATH):
            try:
                self._sface = cv2.FaceRecognizerSF.create(Config.SFACE_MODEL_PATH, "")
            except Exception as e:
                print(f"[ERROR] Failed to load SFace model: {e}")
                self._sface = None

        if os.path.exists(Config.YUNET_MODEL_PATH):
            try:
                self._yunet = cv2.FaceDetectorYN.create(
                    Config.YUNET_MODEL_PATH,
                    "",
                    (320, 320),
                    score_threshold=0.6,
                    nms_threshold=0.3,
                    top_k=5000,
                )
            except Exception as e:
                print(f"[ERROR] Failed to load YuNet model: {e}")
                self._yunet = None

        self._is_loaded = (self._sface is not None)

    @property
    def is_available(self) -> bool:
        """True if SFace model is loaded and ready."""
        return self._sface is not None

    @property
    def has_enrolled_faces(self) -> bool:
        """True if at least one enrolled student has reference embeddings."""
        return len(self._centroids) > 0

    def load_embeddings(self) -> bool:
        """Load stored embeddings from disk (.npz)."""
        if not os.path.exists(Config.SFACE_EMBEDDINGS_PATH):
            return False

        try:
            data = np.load(Config.SFACE_EMBEDDINGS_PATH, allow_pickle=True)
            self._embeddings_db = {}
            self._centroids = {}

            # Format in npz: student_db_ids, embeddings, counts
            student_ids = data.get("student_ids", [])
            centroids = data.get("centroids", [])

            for s_id, c in zip(student_ids, centroids):
                s_id = int(s_id)
                self._centroids[s_id] = c.reshape(1, 128)

            # Check for multi-exemplar dictionary
            if "raw_embeddings_json" in data:
                raw_json = str(data["raw_embeddings_json"])
                meta = json.loads(raw_json)
                for s_id_str, emb_list in meta.items():
                    self._embeddings_db[int(s_id_str)] = [
                        np.array(e, dtype=np.float32).reshape(1, 128) for e in emb_list
                    ]

            return len(self._centroids) > 0
        except Exception as e:
            print(f"[WARN] Failed to load SFace embeddings: {e}")
            return False

    def save_embeddings(self):
        """Persist embeddings and student centroids to disk."""
        if not self._centroids:
            return

        os.makedirs(Config.MODELS_DIR, exist_ok=True)
        student_ids = np.array(list(self._centroids.keys()), dtype=np.int32)
        centroids = np.array([self._centroids[sid].flatten() for sid in student_ids], dtype=np.float32)

        # Store serializable multi-exemplar lists
        raw_json_dict = {}
        for sid, emb_list in self._embeddings_db.items():
            raw_json_dict[str(sid)] = [e.flatten().tolist() for e in emb_list]

        np.savez_compressed(
            Config.SFACE_EMBEDDINGS_PATH,
            student_ids=student_ids,
            centroids=centroids,
            raw_embeddings_json=json.dumps(raw_json_dict),
        )

    def extract_embedding(self, face_img) -> np.ndarray | None:
        """
        Extract a normalized 128-D feature embedding from a face image.
        Accepts any BGR or grayscale face crop.
        Applies YuNet 5-point landmark affine alignment when available for pose invariance.
        """
        if not self.is_available or face_img is None or face_img.size == 0:
            return None

        # Convert grayscale to 3-channel BGR if needed
        if len(face_img.shape) == 2 or face_img.shape[2] == 1:
            bgr = cv2.cvtColor(face_img, cv2.COLOR_GRAY2BGR)
        else:
            bgr = face_img.copy()

        # 1. Attempt YuNet 5-landmark affine alignment
        if self._yunet is not None:
            try:
                h, w = bgr.shape[:2]
                self._yunet.setInputSize((w, h))
                _, detected_faces = self._yunet.detect(bgr)
                if detected_faces is not None and len(detected_faces) > 0:
                    aligned = self._sface.alignCrop(bgr, detected_faces[0])
                    feat = self._sface.feature(aligned)
                    norm = np.linalg.norm(feat)
                    if norm > 1e-6:
                        return feat / norm
            except Exception:
                pass

        # 2. Resilient fallback: direct resize to standard SFace dimensions (112x112)
        aligned_112 = cv2.resize(bgr, (112, 112))
        feat = self._sface.feature(aligned_112)
        norm = np.linalg.norm(feat)
        if norm > 1e-6:
            feat = feat / norm
        return feat

    def update_all_embeddings(self) -> dict:
        """
        Scan face_data/ for all active students and compute their
        reference embeddings and centroids.
        """
        if not self.is_available:
            return {"success": False, "message": "SFace model not initialized."}

        active_students = [s for s in db.get_all_students() if s["status"] == "active"]
        face_data_dir = Config.FACE_DATA_DIR

        self._embeddings_db = {}
        self._centroids = {}
        processed_students = 0
        total_vectors = 0

        for student in active_students:
            sid = student["id"]
            safe_name = sanitize_name_for_filesystem(student["full_name"])
            named_folder = os.path.join(face_data_dir, safe_name)
            legacy_folder = os.path.join(face_data_dir, str(sid))
            s_folder = named_folder if os.path.isdir(named_folder) else legacy_folder

            if not os.path.isdir(s_folder):
                continue

            valid_files = [
                f for f in os.listdir(s_folder)
                if f.lower().endswith((".jpg", ".jpeg", ".png"))
            ]
            if not valid_files:
                continue

            student_embeddings = []
            for f in valid_files:
                p = os.path.join(s_folder, f)
                img = cv2.imread(p)
                if img is None:
                    continue

                emb = self.extract_embedding(img)
                if emb is not None:
                    student_embeddings.append(emb)

            if student_embeddings:
                self._embeddings_db[sid] = student_embeddings
                
                # Compute centroid embedding (mean vector normalized to unit length)
                stacked = np.vstack(student_embeddings)
                centroid = np.mean(stacked, axis=0, keepdims=True)
                centroid = centroid / (np.linalg.norm(centroid) + 1e-6)
                self._centroids[sid] = centroid.astype(np.float32)

                processed_students += 1
                total_vectors += len(student_embeddings)

        self.save_embeddings()

        return {
            "success": True,
            "processed_students": processed_students,
            "total_vectors": total_vectors,
            "message": f"Updated SFace embeddings for {processed_students} student(s) ({total_vectors} total vectors).",
        }

    def predict(self, face_roi, threshold: float = None):
        """
        Predict identity for a face ROI using cosine similarity against
        enrolled student reference embeddings.

        Returns
        -------
        best_student_id : int (-1 if unknown)
        max_similarity : float (in [-1, 1], higher = closer)
        student_info : dict | None
        """
        if not self.is_available or not self._centroids:
            return -1, 0.0, None

        if threshold is None:
            threshold = ModelManager.get_threshold("sface")

        query_emb = self.extract_embedding(face_roi)
        if query_emb is None:
            return -1, 0.0, None

        best_student_id = -1
        max_similarity = -1.0

        # Multi-exemplar + Centroid hybrid matching:
        # Check against centroids first, then verify against individual reference samples
        for sid, centroid in self._centroids.items():
            # Cosine similarity is dot product of normalized vectors
            sim = float(np.dot(query_emb, centroid.T)[0][0])
            
            # If multi-exemplars exist, also test individual exemplar match
            exemplars = self._embeddings_db.get(sid)
            if exemplars:
                exemplar_sims = [float(np.dot(query_emb, e.T)[0][0]) for e in exemplars]
                max_exemplar_sim = max(exemplar_sims)
                # Accurate multi-pose fusion: give credit to best matching enrolled pose
                # while incorporating centroid consistency
                combined_sim = max(max_exemplar_sim, 0.7 * max_exemplar_sim + 0.3 * sim)
            else:
                combined_sim = sim

            if combined_sim > max_similarity:
                max_similarity = combined_sim
                best_student_id = sid

        # Check threshold
        if max_similarity >= threshold and best_student_id != -1:
            student_info = ModelManager.resolve_student_id(best_student_id)
            if student_info:
                return best_student_id, max_similarity, student_info

        return -1, max_similarity, None
