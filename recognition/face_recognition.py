"""
SMART ENTRY — SFace Deep Face Recognition Module
Utilizes OpenCV SFace (128-dimensional deep feature metric embeddings)
with YuNet face alignment for high-accuracy contactless verification and stranger rejection.
"""
import os
import cv2
from config import Config
from recognition.model_manager import ModelManager
from recognition.sface_recognizer import SFaceRecognizer


class FaceRecognizer:
    """
    Dedicated face recognizer powered by OpenCV SFace deep neural network (128-D embeddings).
    Matches query faces using Cosine Similarity metric comparison.
    """

    def __init__(self):
        self._sface_recognizer = None
        self.load_model()

    def load_model(self) -> bool:
        """Load SFace deep learning recognizer and enrolled embeddings."""
        try:
            self._sface_recognizer = SFaceRecognizer()
            return self._sface_recognizer.is_available
        except Exception as e:
            print(f"[ERROR] Failed to load SFace Recognizer: {e}")
            self._sface_recognizer = None
            return False

    @property
    def active_model(self) -> str:
        """Return active model name ('sface')."""
        return "sface"

    @property
    def is_ready(self) -> bool:
        """True if SFace is loaded and has enrolled face embeddings ready."""
        return (
            self._sface_recognizer is not None
            and self._sface_recognizer.is_available
            and self._sface_recognizer.has_enrolled_faces
        )

    def get_threshold(self) -> float:
        """Return calibrated SFace cosine similarity threshold."""
        return ModelManager.get_threshold("sface")

    def is_recognized(self, score: float) -> bool:
        """
        Check if the cosine similarity score meets or exceeds the calibrated threshold.
        """
        threshold = self.get_threshold()
        return score >= threshold

    def predict(self, face_roi):
        """
        Predict student identity for a cropped face region using SFace deep embeddings.

        Parameters
        ----------
        face_roi : np.ndarray
            Cropped face image.

        Returns
        -------
        label : int
            Student DB id if recognized, -1 if unknown / rejected.
        score : float
            Cosine Similarity score (0.0 to 1.0, higher = closer match).
        student_info : dict | None
            Student record metadata if recognized.
        """
        if not self._sface_recognizer or not self._sface_recognizer.is_available:
            return -1, 0.0, None

        sid, sim, student_info = self._sface_recognizer.predict(face_roi)
        return sid, round(float(sim), 4), student_info
