"""
SMART ENTRY — Attendance Routes
View, filter, and export attendance logs. Also exposes analytics data
for Chart.js charts on the analytics page.
"""
import csv
import io
from datetime import datetime, timedelta
from flask import Blueprint, render_template, request, Response, jsonify, url_for
from flask_login import login_required
from database import database as db

attendance_bp = Blueprint("attendance", __name__)

PROGRAMS = [
    # CEIT (College of Engineering and Information Technology)
    "BSIT", "BSEE", "BSCPE", "EET",
    # CITTE (College of Industrial Technology and Teacher Education)
    "BSIT-ADT", "BSIT-AT", "BSIT-CT", "BSIT-ET", "BSIT-ELT",
    "BSIT-FPSMT", "BSIT-GFDT", "BSIT-WFT",
    "BTVTED-AD", "BTVTED-AT", "BTVTED-CCT", "BTVTED-ET", "BTVTED-ELT",
    "BTVTED-FSM", "BTVTED-GFD", "BTVTED-WFT",
    "BTLED-HE", "BTLED-IA",
    # CTHM (College of Tourism and Hospitality Management)
    "BSTM", "BSHM", "BSFBSM",
    # CBA (College of Business and Accountancy)
    "BSA", "BSMA", "BSOA", "BSBA", "BSENTREP",
    # Institutional & Staff
    "Faculty/Employee", "Library-Staff", "Others",
    # Guests & Visitors
    "Guest", "Visiting-Researcher", "Community-User",
]
PURPOSES = ["Return Book", "Borrow Book", "Study Room", "General Space"]


@attendance_bp.route("/admin/attendance")
@login_required
def attendance_page():
    date_from = request.args.get("date_from", "").strip()
    date_to = request.args.get("date_to", "").strip()
    program = request.args.get("program", "").strip()
    purpose = request.args.get("purpose", "").strip()
    search = request.args.get("search", "").strip()
    is_ajax = request.args.get("ajax") == "1" or request.headers.get("X-Requested-With") == "XMLHttpRequest"

    logs = db.get_attendance_logs(
        date_from=date_from or None,
        date_to=date_to or None,
        program=program or None,
        purpose=purpose or None,
        search=search or None,
        limit=5000,
    )

    if is_ajax:
        log_list = []
        for log in logs:
            log_list.append({
                "id": log["id"],
                "full_name": log["full_name"],
                "student_id": log["student_id"],
                "program": log["program"],
                "date": log["date"],
                "time_in": log["time_in"],
                "time_out": log["time_out"],
                "visit_purpose": log["visit_purpose"],
            })

        export_params = {k: v for k, v in [
            ("date_from", date_from),
            ("date_to", date_to),
            ("program", program),
            ("purpose", purpose),
            ("search", search)
        ] if v}

        return jsonify({
            "status": "success",
            "count": len(logs),
            "logs": log_list,
            "export_url": url_for("attendance.export_csv", **export_params)
        })

    return render_template(
        "admin/attendance.html",
        logs=logs,
        programs=PROGRAMS,
        purposes=PURPOSES,
        filters={"date_from": date_from, "date_to": date_to,
                 "program": program, "purpose": purpose, "search": search},
    )


@attendance_bp.route("/admin/attendance/export")
@login_required
def export_csv():
    date_from = request.args.get("date_from")
    date_to = request.args.get("date_to")
    program = request.args.get("program")
    purpose = request.args.get("purpose")
    search = request.args.get("search")

    logs = db.get_attendance_logs(
        date_from=date_from or None, date_to=date_to or None,
        program=program or None, purpose=purpose or None, search=search or None,
        limit=10000,
    )

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["#", "Full Name", "Student ID", "Program",
                     "Date", "Time In", "Visit Purpose"])
    for i, row in enumerate(logs, 1):
        writer.writerow([
            i, row["full_name"], row["student_id"], row["program"],
            row["date"], row["time_in"],
            row["visit_purpose"] or "—",
        ])

    filename = f"smart_entry_attendance_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
    return Response(
        output.getvalue(),
        mimetype="text/csv",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )


# ── Analytics / Charts ────────────────────────────────────────────────────────

@attendance_bp.route("/admin/analytics")
@login_required
def analytics_page():
    today = datetime.now().strftime("%Y-%m-%d")
    week_ago = (datetime.now() - timedelta(days=6)).strftime("%Y-%m-%d")
    return render_template("admin/analytics.html",
                           today=today, week_ago=week_ago)


@attendance_bp.route("/admin/analytics/hourly")
@login_required
def hourly_json():
    date = request.args.get("date", datetime.now().strftime("%Y-%m-%d"))
    rows = db.get_hourly_traffic(date)
    hours = [f"{h:02d}:00" for h in range(24)]
    counts = [0] * 24
    for row in rows:
        h = int(row["hour"])
        counts[h] = row["count"]
    return jsonify({"labels": hours, "data": counts})


@attendance_bp.route("/admin/analytics/purpose")
@login_required
def purpose_json():
    date_from = request.args.get("date_from")
    date_to = request.args.get("date_to")
    rows = db.get_purpose_breakdown(date_from=date_from, date_to=date_to)
    labels = [row["visit_purpose"] for row in rows]
    data = [row["count"] for row in rows]
    return jsonify({"labels": labels, "data": data})


@attendance_bp.route("/admin/analytics/department")
@login_required
def department_json():
    """Return department/program breakdown ordered by visit count descending."""
    date_from = request.args.get("date_from")
    date_to = request.args.get("date_to")
    rows = db.get_department_breakdown(date_from=date_from, date_to=date_to)
    labels = [row["department"] for row in rows]
    data = [row["count"] for row in rows]
    highest = db.get_highest_visiting_department(date_from=date_from, date_to=date_to)
    return jsonify({
        "labels": labels,
        "data": data,
        "highest": highest,
    })


@attendance_bp.route("/admin/analytics/daily")
@login_required
def daily_json():
    """Return daily visitor counts for the last N days."""
    days = int(request.args.get("days", 7))
    results = []
    labels = []
    from database.database import get_db_connection
    conn = get_db_connection()
    for i in range(days - 1, -1, -1):
        day = (datetime.now() - timedelta(days=i)).strftime("%Y-%m-%d")
        count = conn.execute(
            "SELECT COUNT(*) FROM attendance_logs WHERE date = ?", (day,)
        ).fetchone()[0]
        labels.append(day)
        results.append(count)
    conn.close()
    return jsonify({"labels": labels, "data": results})
