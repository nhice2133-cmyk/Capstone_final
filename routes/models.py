"""
SMART ENTRY — Admin SFace Model Management & Evaluation Routes
Provides administrator visibility and control over:
- OpenCV SFace deep facial feature embeddings (128-D)
- Cosine similarity threshold calibration and adjustments
- Model metadata and feature embedding updates
- Independent benchmark evaluation and confusion matrix reporting
"""
import os
import json
from flask import Blueprint, render_template, request, jsonify, redirect, url_for, flash
from flask_login import login_required
from config import Config
from recognition.model_manager import ModelManager
from recognition.training import train_model, get_training_stats
from recognition.evaluation import RecognitionEvaluator
from routes.kiosk import _reload_recognizer

models_bp = Blueprint("models", __name__)


@models_bp.route("/admin/models", methods=["GET"])
@login_required
def models_dashboard():
    """Renders the SFace Deep Learning Model Management & Validation Dashboard."""
    stats = get_training_stats()
    metadata = ModelManager.get_metadata()

    # Load latest evaluation report if available
    eval_file = os.path.join(Config.BASE_DIR, "recognition", "evaluation", "evaluation_results.json")
    evaluation_data = None
    if os.path.exists(eval_file):
        try:
            with open(eval_file, "r", encoding="utf-8") as f:
                evaluation_data = json.load(f)
        except Exception as e:
            print(f"[WARN] Failed to load evaluation report: {e}")

    return render_template(
        "admin/models.html",
        stats=stats,
        meta=metadata,
        evaluation=evaluation_data,
    )


@models_bp.route("/admin/models/set_active", methods=["POST"])
@login_required
def set_active_model():
    """Confirms active model is SFace."""
    ModelManager.set_active_model_type("sface")
    _reload_recognizer()
    flash("Active recognition engine is SFace Deep Feature Embeddings.", "info")
    return redirect(url_for("models.models_dashboard"))


@models_bp.route("/admin/models/set_threshold", methods=["POST"])
@login_required
def set_threshold():
    """Adjust SFace recognition cosine similarity threshold."""
    try:
        threshold = float(request.form.get("threshold", 0.363))
    except (ValueError, TypeError):
        flash("Invalid threshold number provided.", "danger")
        return redirect(url_for("models.models_dashboard"))

    success = ModelManager.set_threshold("sface", threshold)
    if success:
        _reload_recognizer()
        flash(f"Updated SFace Cosine Similarity Threshold to {threshold}.", "success")
    else:
        flash("Failed to update threshold.", "danger")
    return redirect(url_for("models.models_dashboard"))


@models_bp.route("/admin/models/retrain", methods=["POST"])
@login_required
def retrain():
    """Extract SFace 128-D deep feature embeddings from enrolled faces."""
    res = train_model()
    _reload_recognizer()

    # If called via AJAX/fetch, return JSON directly for animated feedback
    if request.headers.get("X-Requested-With") == "XMLHttpRequest" or request.is_json:
        return jsonify(res)

    if res.get("success"):
        flash(res.get("message"), "success")
    else:
        flash(f"Training failed: {res.get('message')}", "danger")
    return redirect(url_for("models.models_dashboard"))


@models_bp.route("/admin/models/evaluate", methods=["POST"])
@login_required
def run_evaluation():
    """Trigger the independent benchmark evaluation suite."""
    evaluator = RecognitionEvaluator()
    try:
        results = evaluator.run_benchmark(num_enrolled=10, train_per_subject=6, test_per_subject=4, num_strangers=30)
        
        meta = ModelManager.get_metadata()
        meta["last_evaluation"] = {
            "date": results.get("dataset_info"),
            "sface_acc": results.get("sface_evaluation", {}).get("metrics_at_recommended_threshold", {}).get("correct_id_rate") if results.get("sface_evaluation") else None,
        }
        ModelManager.save_metadata(meta)
        flash("Benchmark evaluation completed successfully! Results updated below.", "success")
    except Exception as e:
        flash(f"Evaluation error: {e}", "danger")

    return redirect(url_for("models.models_dashboard"))
