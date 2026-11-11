"""
SMART ENTRY — Recognition Validation & Evaluation Framework
Provides rigorous, repeatable evaluation without data leakage, measuring:
- Correct Identification Rate (Rank-1 Accuracy)
- False Acceptance Rate (FAR)
- False Rejection Rate (FRR)
- Unknown-Person Rejection Rate
- Inference Latency (ms)
- Identity Confusion Matrix
- Threshold Sensitivity Curves (FAR vs FRR)
"""
import os
import cv2
import time
import json
import numpy as np
from config import Config
from recognition.face_detection import FaceDetector


class RecognitionEvaluator:
    """
    Rigorously benchmarks face recognition models (LBPH vs SFace)
    on an independent evaluation partition with registered and unregistered subjects.
    """

    def __init__(self, dataset_dir=None):
        if dataset_dir is None:
            dataset_dir = os.path.join(Config.BASE_DIR, "recognition", "evaluation", "benchmark_dataset")
        self.dataset_dir = dataset_dir

    def run_benchmark(self, num_enrolled=10, train_per_subject=6, test_per_subject=4, num_strangers=30):
        """
        Executes an end-to-end evaluation comparing LBPH and SFace
        with zero data leakage.
        """
        # 1. Discover subject directories
        subject_dirs = sorted([
            d for d in os.listdir(self.dataset_dir)
            if os.path.isdir(os.path.join(self.dataset_dir, d)) and d.startswith("s")
        ])

        if len(subject_dirs) < num_enrolled + num_strangers:
            # Fallback if fewer directories
            num_enrolled = min(num_enrolled, len(subject_dirs) // 2)
            num_strangers = len(subject_dirs) - num_enrolled

        enrolled_subjects = subject_dirs[:num_enrolled]
        stranger_subjects = subject_dirs[num_enrolled : num_enrolled + num_strangers]

        # 2. Partition datasets (Strict Train / Val separation)
        train_faces_lbph = []
        train_labels_lbph = []
        train_images_sface = {}  # subject_id -> list of BGR images
        
        val_enrolled_images = []  # list of (subject_id, image)
        val_stranger_images = []  # list of image

        # Load enrolled subjects
        for idx, subj in enumerate(enrolled_subjects):
            subj_path = os.path.join(self.dataset_dir, subj)
            all_files = sorted([
                f for f in os.listdir(subj_path)
                if f.lower().endswith((".pgm", ".jpg", ".jpeg", ".png"))
            ])

            train_files = all_files[:train_per_subject]
            test_files = all_files[train_per_subject : train_per_subject + test_per_subject]

            label = idx + 1
            train_images_sface[label] = []

            for f in train_files:
                p = os.path.join(subj_path, f)
                img = cv2.imread(p)
                if img is None:
                    continue
                # Preprocess for LBPH
                roi_lbph = FaceDetector.preprocess_face_lbph(img, (200, 200))
                train_faces_lbph.append(roi_lbph)
                train_labels_lbph.append(label)
                # Store BGR for SFace
                train_images_sface[label].append(img)

            for f in test_files:
                p = os.path.join(subj_path, f)
                img = cv2.imread(p)
                if img is not None:
                    val_enrolled_images.append((label, img))

        # Load stranger subjects (unregistered)
        for subj in stranger_subjects:
            subj_path = os.path.join(self.dataset_dir, subj)
            all_files = sorted([
                f for f in os.listdir(subj_path)
                if f.lower().endswith((".pgm", ".jpg", ".jpeg", ".png"))
            ])
            # Use 2 images per stranger
            for f in all_files[:2]:
                p = os.path.join(subj_path, f)
                img = cv2.imread(p)
                if img is not None:
                    val_stranger_images.append(img)

        # 3. Train LBPH model
        lbph_model = cv2.face.LBPHFaceRecognizer_create(radius=1, neighbors=8, grid_x=8, grid_y=8)
        lbph_model.train(train_faces_lbph, np.array(train_labels_lbph))

        # 4. Train SFace Embeddings
        from recognition.sface_recognizer import SFaceRecognizer
        sface_obj = SFaceRecognizer()
        sface_available = sface_obj.is_available
        sface_centroids = {}
        sface_exemplars = {}

        if sface_available:
            for label, imgs in train_images_sface.items():
                embs = [sface_obj.extract_embedding(im) for im in imgs]
                embs = [e for e in embs if e is not None]
                if embs:
                    sface_exemplars[label] = embs
                    stacked = np.vstack(embs)
                    centroid = np.mean(stacked, axis=0, keepdims=True)
                    centroid = centroid / (np.linalg.norm(centroid) + 1e-6)
                    sface_centroids[label] = centroid

        # 5. Evaluate LBPH
        lbph_results = self._evaluate_model(
            model_name="LBPH",
            model_type="lbph",
            predict_fn=lambda im: self._predict_lbph(lbph_model, im),
            thresholds=list(range(40, 95, 2)),
            val_enrolled=val_enrolled_images,
            val_strangers=val_stranger_images,
            enrolled_labels=list(range(1, num_enrolled + 1)),
        )

        # 6. Evaluate SFace
        sface_results = None
        if sface_available and sface_centroids:
            sface_thresholds = [round(x, 2) for x in np.arange(0.20, 0.72, 0.02)]
            sface_results = self._evaluate_model(
                model_name="OpenCV SFace",
                model_type="sface",
                predict_fn=lambda im: self._predict_sface(sface_obj, sface_centroids, sface_exemplars, im),
                thresholds=sface_thresholds,
                val_enrolled=val_enrolled_images,
                val_strangers=val_stranger_images,
                enrolled_labels=list(range(1, num_enrolled + 1)),
            )

        summary = {
            "dataset_info": {
                "num_enrolled_subjects": num_enrolled,
                "train_images_per_subject": train_per_subject,
                "total_train_images": len(train_faces_lbph),
                "val_enrolled_attempts": len(val_enrolled_images),
                "val_stranger_attempts": len(val_stranger_images),
                "total_eval_attempts": len(val_enrolled_images) + len(val_stranger_images),
            },
            "lbph_evaluation": lbph_results,
            "sface_evaluation": sface_results,
        }

        # Save results to disk
        out_dir = os.path.join(Config.BASE_DIR, "recognition", "evaluation")
        os.makedirs(out_dir, exist_ok=True)
        out_file = os.path.join(out_dir, "evaluation_results.json")
        with open(out_file, "w", encoding="utf-8") as f:
            json.dump(summary, f, indent=2)

        return summary

    def _predict_lbph(self, model, bgr_img):
        preprocessed = FaceDetector.preprocess_face_lbph(bgr_img, (200, 200))
        label, distance = model.predict(preprocessed)
        return int(label), float(distance)

    def _predict_sface(self, sface_obj, centroids, exemplars, bgr_img):
        emb = sface_obj.extract_embedding(bgr_img)
        if emb is None:
            return -1, 0.0

        best_label = -1
        max_sim = -1.0
        for label, centroid in centroids.items():
            sim = float(np.dot(emb, centroid.T)[0][0])
            # Check exemplars
            exs = exemplars.get(label, [])
            if exs:
                ex_sims = [float(np.dot(emb, e.T)[0][0]) for e in exs]
                combined = 0.7 * max(ex_sims) + 0.3 * sim
            else:
                combined = sim

            if combined > max_sim:
                max_sim = combined
                best_label = label

        return best_label, max_sim

    def _evaluate_model(self, model_name, model_type, predict_fn, thresholds, val_enrolled, val_strangers, enrolled_labels):
        """
        Computes accuracy, FAR, FRR, Unknown Rejection, Latency, and Confusion Matrix
        across multiple candidate thresholds.
        """
        # Pre-calculate predictions and latencies for all validation samples
        enrolled_predictions = []
        latencies = []

        for true_label, img in val_enrolled:
            t0 = time.perf_counter()
            pred_label, score = predict_fn(img)
            latencies.append((time.perf_counter() - t0) * 1000.0)
            enrolled_predictions.append((true_label, pred_label, score))

        stranger_predictions = []
        for img in val_strangers:
            t0 = time.perf_counter()
            pred_label, score = predict_fn(img)
            latencies.append((time.perf_counter() - t0) * 1000.0)
            stranger_predictions.append((pred_label, score))

        avg_latency_ms = round(float(np.mean(latencies)), 2)

        threshold_sweep = []
        best_threshold = None
        best_f1 = -1.0
        best_metrics = {}

        for th in thresholds:
            correct_id_count = 0
            false_rejection_count = 0
            identity_confusion_count = 0
            false_acceptance_strangers = 0

            # 1. Enrolled validation
            for true_label, pred_label, score in enrolled_predictions:
                accepted = (score <= th) if model_type == "lbph" else (score >= th)
                if accepted:
                    if pred_label == true_label:
                        correct_id_count += 1
                    else:
                        identity_confusion_count += 1
                else:
                    false_rejection_count += 1

            # 2. Stranger validation
            for pred_label, score in stranger_predictions:
                accepted = (score <= th) if model_type == "lbph" else (score >= th)
                if accepted:
                    false_acceptance_strangers += 1

            total_enrolled = len(enrolled_predictions)
            total_strangers = len(stranger_predictions)

            correct_id_rate = round((correct_id_count / total_enrolled) * 100.0, 2)
            false_rejection_rate = round((false_rejection_count / total_enrolled) * 100.0, 2)
            identity_confusion_rate = round((identity_confusion_count / total_enrolled) * 100.0, 2)
            
            stranger_far = round((false_acceptance_strangers / total_strangers) * 100.0, 2)
            unknown_rejection_rate = round(((total_strangers - false_acceptance_strangers) / total_strangers) * 100.0, 2)

            # Overall FAR: (incorrect identity matches on enrolled + accepted strangers) / total attempts
            total_imposters = identity_confusion_count + false_acceptance_strangers
            total_non_match_opps = (total_enrolled - correct_id_count) + total_strangers
            far_rate = round((total_imposters / (total_enrolled + total_strangers)) * 100.0, 2)

            # Balanced score to find optimal operating threshold (high correct ID, low FAR and low FRR)
            score_metric = (2 * correct_id_rate) - (3 * far_rate) - false_rejection_rate

            sweep_item = {
                "threshold": th,
                "correct_id_rate": correct_id_rate,
                "false_rejection_rate": false_rejection_rate,
                "identity_confusion_rate": identity_confusion_rate,
                "unknown_rejection_rate": unknown_rejection_rate,
                "stranger_far": stranger_far,
                "overall_far": far_rate,
            }
            threshold_sweep.append(sweep_item)

            if score_metric > best_f1:
                best_f1 = score_metric
                best_threshold = th
                best_metrics = sweep_item

        # Compute Confusion Matrix at best recommended threshold
        labels_all = enrolled_labels + ["Unknown"]
        matrix = {str(r): {str(c): 0 for c in labels_all} for r in labels_all}

        for true_label, pred_label, score in enrolled_predictions:
            accepted = (score <= best_threshold) if model_type == "lbph" else (score >= best_threshold)
            pred_key = str(pred_label) if accepted else "Unknown"
            matrix[str(true_label)][pred_key] += 1

        for pred_label, score in stranger_predictions:
            accepted = (score <= best_threshold) if model_type == "lbph" else (score >= best_threshold)
            pred_key = str(pred_label) if accepted else "Unknown"
            matrix["Unknown"][pred_key] += 1

        return {
            "model_name": model_name,
            "model_type": model_type,
            "recommended_threshold": best_threshold,
            "average_recognition_time_ms": avg_latency_ms,
            "metrics_at_recommended_threshold": best_metrics,
            "confusion_matrix": matrix,
            "threshold_sweep": threshold_sweep,
        }
