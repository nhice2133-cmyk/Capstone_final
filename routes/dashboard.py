"""
SMART ENTRY — Dashboard Routes
Admin home page and real-time summary stats.
"""
from flask import Blueprint, render_template, jsonify
from flask_login import login_required
from database import database as db

dashboard_bp = Blueprint("dashboard", __name__)


@dashboard_bp.route("/admin")
@dashboard_bp.route("/admin/dashboard")
@login_required
def home():
    stats = {
        "today_visitors": db.get_todays_visitor_count(),
        "currently_inside": db.get_currently_inside_count(),
        "pending_alerts": db.count_unresolved_alerts(),
        "total_enrolled": db.count_students(),
    }
    recent_logs = db.get_recent_logs(limit=8)
    return render_template("admin/dashboard.html", stats=stats, recent_logs=recent_logs)


@dashboard_bp.route("/admin/stats/json")
@login_required
def stats_json():
    """AJAX endpoint — returns live summary stats for auto-refresh."""
    return jsonify({
        "today_visitors": db.get_todays_visitor_count(),
        "currently_inside": db.get_currently_inside_count(),
        "pending_alerts": db.count_unresolved_alerts(),
        "total_enrolled": db.count_students(),
    })
