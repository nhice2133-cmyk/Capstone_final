"""
SMART ENTRY — Face Detection & Preprocessing Module
Wraps OpenCV's Haar Cascade Classifier for real-time face detection,
face quality validation (blur, lighting, size), and standardized CLAHE preprocessing.
"""
import os
import cv2
import numpy as np
from config import Config


class FaceDetector:
    """
    Detects frontal faces in a grayscale image using the Haar Cascade
    Classifier. Returns bounding boxes for all detected faces.
    Also provides standardized localized preprocessing and quality audits.
    """

    def __init__(self):
        if not os.path.exists(Config.HAAR_CASCADE_PATH):
            raise FileNotFoundError(
                f"Haar Cascade XML not found at: {Config.HAAR_CASCADE_PATH}\n"
                "Please place haarcascade_frontalface_default.xml in "
                "recognition/haarcascade/"
            )
        self._classifier = cv2.CascadeClassifier(Config.HAAR_CASCADE_PATH)
        self._yunet = None
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
            except Exception:
                self._yunet = None

    def detect(self, frame, min_size=None):
        """
        High-speed hybrid multi-scale face detection in a BGR frame.
        1. Fast Haar Cascade with 0.5x pyramid downscaling (ultra-fast ~15ms).
        2. YuNet deep neural detector fallback if Haar misses (high recall across angles/tilts).
        """
        if min_size is None:
            min_size = (45, 45)

        h, w = frame.shape[:2]
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)

        # High-speed pyramid downscaling for frames >= 480px width
        if w >= 480:
            scale = 0.5
            small_gray = cv2.resize(gray, (0, 0), fx=scale, fy=scale, interpolation=cv2.INTER_LINEAR)
            det_gray = cv2.equalizeHist(small_gray)
            scaled_min = (max(20, int(min_size[0] * scale)), max(20, int(min_size[1] * scale)))
            faces_small = self._classifier.detectMultiScale(
                det_gray,
                scaleFactor=1.1,
                minNeighbors=4,
                minSize=scaled_min,
                flags=cv2.CASCADE_SCALE_IMAGE,
            )
            inv_scale = 1.0 / scale
            faces = [(int(x * inv_scale), int(y * inv_scale), int(fw * inv_scale), int(fh * inv_scale))
                     for (x, y, fw, fh) in faces_small]
        else:
            det_gray = cv2.equalizeHist(gray)
            faces = self._classifier.detectMultiScale(
                det_gray,
                scaleFactor=1.1,
                minNeighbors=4,
                minSize=min_size,
                flags=cv2.CASCADE_SCALE_IMAGE,
            )
            faces = list(faces)

        # Deep neural fallback: If Haar missed due to face angle, tilt, or tight crop, invoke YuNet
        if len(faces) == 0 and self._yunet is not None:
            try:
                self._yunet.setInputSize((w, h))
                _, yn_faces = self._yunet.detect(frame)
                if yn_faces is not None and len(yn_faces) > 0:
                    faces = [(int(f[0]), int(f[1]), int(f[2]), int(f[3])) for f in yn_faces]
            except Exception:
                pass

        if len(faces) == 0:
            return [], gray
        return faces, gray

    @staticmethod
    def draw_rectangles(frame, faces, color=(0, 255, 0), thickness=2):
        """Draw bounding rectangles on a frame for visualization."""
        for (x, y, w, h) in faces:
            cv2.rectangle(frame, (x, y), (x + w, y + h), color, thickness)
        return frame

    @staticmethod
    def preprocess_face(face_img, target_size=(200, 200)):
        """
        Consistent, high-quality facial contrast normalization preprocessing.
        Applies Contrast Limited Adaptive Histogram Equalization (CLAHE)
        to normalize localized lighting without washing out facial features,
        followed by bilateral filtering to suppress camera sensor noise.
        """
        if face_img is None or face_img.size == 0:
            return np.zeros(target_size, dtype=np.uint8)

        if len(face_img.shape) == 3:
            gray = cv2.cvtColor(face_img, cv2.COLOR_BGR2GRAY)
        else:
            gray = face_img.copy()

        # CLAHE (Contrast Limited Adaptive Histogram Equalization)
        # Prevents over-amplification of noise while balancing shadow/highlight variations
        clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
        enhanced = clahe.apply(gray)

        # Bilateral filter to smooth sensor grain while maintaining sharp edge boundaries
        smoothed = cv2.bilateralFilter(enhanced, d=5, sigmaColor=25, sigmaSpace=25)

        return cv2.resize(smoothed, target_size)

    # Backward compatibility alias
    preprocess_face_lbph = preprocess_face

    @staticmethod
    def crop_face(frame_or_gray, face_bbox, apply_preprocessing=False, target_size=(200, 200), padding_pct=0.12):
        """
        Crop and optionally preprocess a face region for the recognizer.
        Supports both natural color BGR frames and grayscale images.
        Includes proportionate margin padding to preserve facial landmarks (eyes, chin, temples)
        for deep neural alignment (YuNet affine warping).
        """
        x, y, w, h = int(face_bbox[0]), int(face_bbox[1]), int(face_bbox[2]), int(face_bbox[3])
        h_img, w_img = frame_or_gray.shape[:2]

        pad_x = int(w * padding_pct)
        pad_y = int(h * padding_pct)

        x1 = max(0, x - pad_x)
        y1 = max(0, y - pad_y)
        x2 = min(w_img, x + w + pad_x)
        y2 = min(h_img, y + h + pad_y)

        face_roi = frame_or_gray[y1:y2, x1:x2]
        if face_roi.size == 0:
            if len(frame_or_gray.shape) == 3:
                return np.zeros((target_size[1], target_size[0], 3), dtype=np.uint8)
            return np.zeros(target_size, dtype=np.uint8)

        if apply_preprocessing:
            return FaceDetector.preprocess_face(face_roi, target_size)
        return cv2.resize(face_roi, target_size)

    @staticmethod
    def validate_face_quality(frame, face_bbox):
        """
        Audit detected face image against quality standards:
        - Minimum dimensions
        - Sharpness / Blur score (Laplacian variance)
        - Illumination (darkness / severe overexposure)

        Returns
        -------
        is_valid : bool
        reason : str
        metrics : dict
        """
        x, y, w, h = int(face_bbox[0]), int(face_bbox[1]), int(face_bbox[2]), int(face_bbox[3])
        min_w, min_h = Config.ENROLLMENT_MIN_FACE_SIZE

        # 1. Size Check
        if w < min_w or h < min_h:
            return False, f"Face too small ({w}x{h}). Please move closer to the camera.", {
                "width": int(w), "height": int(h)
            }

        # Crop face for quality inspection
        h_img, w_img = frame.shape[:2]
        x1, y1 = max(0, x), max(0, y)
        x2, y2 = min(w_img, x + w), min(h_img, y + h)
        crop = frame[y1:y2, x1:x2]

        if crop.size == 0:
            return False, "Invalid face region.", {}

        if len(crop.shape) == 3:
            gray_crop = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY)
        else:
            gray_crop = crop

        # 2. Blur / Sharpness check using Laplacian variance
        laplacian_var = float(cv2.Laplacian(gray_crop, cv2.CV_64F).var())
        if laplacian_var < Config.ENROLLMENT_BLUR_THRESHOLD:
            return False, f"Face is blurry ({laplacian_var:.1f}). Please hold steady.", {
                "blur_score": laplacian_var
            }

        # 3. Illumination checks
        mean_brightness = float(np.mean(gray_crop))
        if mean_brightness < Config.ENROLLMENT_MIN_BRIGHTNESS:
            return False, f"Lighting is too dark ({mean_brightness:.1f}). Increase light.", {
                "brightness": mean_brightness
            }

        if mean_brightness > Config.ENROLLMENT_MAX_BRIGHTNESS:
            return False, f"Lighting is too bright / overexposed ({mean_brightness:.1f}).", {
                "brightness": mean_brightness
            }

        # Check for severe glare/clipping (more than 15% pixels saturated at 250+)
        overexposed_ratio = float(np.mean(gray_crop >= 250))
        if overexposed_ratio > 0.15:
            return False, f"Severe glare or flash on face ({overexposed_ratio*100:.1f}% saturated).", {
                "glare_ratio": overexposed_ratio
            }

        return True, "Face quality acceptable.", {
            "width": int(w),
            "height": int(h),
            "blur_score": laplacian_var,
            "brightness": mean_brightness,
            "glare_ratio": overexposed_ratio,
        }

    @staticmethod
    def calculate_frame_difference(img1, img2):
        """
        Calculate normalized mean squared difference between two face images
        to check if consecutive frames are too identical.
        """
        if img1 is None or img2 is None:
            return 999.0
        
        # Resize to standard comparison size
        i1 = cv2.resize(img1, (100, 100)).astype("float32")
        i2 = cv2.resize(img2, (100, 100)).astype("float32")
        
        mse = float(np.mean((i1 - i2) ** 2))
        return mse
