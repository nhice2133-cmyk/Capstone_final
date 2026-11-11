"""
SMART ENTRY — Database Layer
Handles SQLite schema creation and all CRUD operations.
Tables: students, attendance_logs, security_alerts, admins
"""
import sqlite3
import os
from datetime import datetime, timedelta
from config import Config


def get_db_connection():
    """Return a sqlite3 connection with row_factory set to Row."""
    conn = sqlite3.connect(Config.DATABASE_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db():
    """Create tables if they do not already exist."""
    os.makedirs(os.path.dirname(Config.DATABASE_PATH), exist_ok=True)
    conn = get_db_connection()
    c = conn.cursor()

    # ── Students (enrolled users) ─────────────────────────────────────────
    c.execute("""
        CREATE TABLE IF NOT EXISTS students (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            full_name   TEXT    NOT NULL,
            student_id  TEXT    NOT NULL UNIQUE,
            program     TEXT    NOT NULL,
            status      TEXT    NOT NULL DEFAULT 'active',
            enrolled_at TEXT    NOT NULL DEFAULT (datetime('now','localtime'))
        )
    """)

    # ── Attendance Logs ───────────────────────────────────────────────────
    c.execute("""
        CREATE TABLE IF NOT EXISTS attendance_logs (
            id             INTEGER PRIMARY KEY AUTOINCREMENT,
            student_db_id  INTEGER NOT NULL REFERENCES students(id),
            date           TEXT    NOT NULL,
            time_in        TEXT    NOT NULL,
            time_out       TEXT,
            visit_purpose  TEXT,
            node           TEXT    NOT NULL DEFAULT 'entry'
        )
    """)

    # ── Security Alerts ───────────────────────────────────────────────────
    c.execute("""
        CREATE TABLE IF NOT EXISTS security_alerts (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            detected_at     TEXT    NOT NULL DEFAULT (datetime('now','localtime')),
            snapshot_path   TEXT,
            confidence_score REAL,
            resolved        INTEGER NOT NULL DEFAULT 0
        )
    """)

    # ── Admins ────────────────────────────────────────────────────────────
    c.execute("""
        CREATE TABLE IF NOT EXISTS admins (
            id                    INTEGER PRIMARY KEY AUTOINCREMENT,
            username              TEXT    NOT NULL UNIQUE,
            password_hash         TEXT    NOT NULL,
            security_question     TEXT    DEFAULT 'What is the official name of the CSUCC library building?',
            security_answer_hash  TEXT,
            recovery_key_hash     TEXT,
            created_at            TEXT    NOT NULL DEFAULT (datetime('now','localtime'))
        )
    """)

    # Ensure recovery columns exist in existing database schemas
    existing_admin_cols = [row[1] for row in c.execute("PRAGMA table_info(admins)").fetchall()]
    if "security_question" not in existing_admin_cols:
        c.execute("ALTER TABLE admins ADD COLUMN security_question TEXT DEFAULT 'What is the official name of the CSUCC library building?'")
    if "security_answer_hash" not in existing_admin_cols:
        c.execute("ALTER TABLE admins ADD COLUMN security_answer_hash TEXT")
    if "recovery_key_hash" not in existing_admin_cols:
        c.execute("ALTER TABLE admins ADD COLUMN recovery_key_hash TEXT")

    conn.commit()
    conn.close()


# ══════════════════════════════════════════════════════════════════════════════
# Student CRUD
# ══════════════════════════════════════════════════════════════════════════════

def create_student(full_name: str, student_id: str, program: str) -> int:
    """Insert a new student. Returns the new row id."""
    conn = get_db_connection()
    c = conn.cursor()
    c.execute(
        "INSERT INTO students (full_name, student_id, program) VALUES (?, ?, ?)",
        (full_name, student_id, program),
    )
    conn.commit()
    new_id = c.lastrowid
    conn.close()
    return new_id


def get_all_students():
    conn = get_db_connection()
    rows = conn.execute(
        "SELECT * FROM students ORDER BY full_name ASC"
    ).fetchall()
    conn.close()
    return rows


def get_student_by_db_id(db_id: int):
    conn = get_db_connection()
    row = conn.execute("SELECT * FROM students WHERE id = ?", (db_id,)).fetchone()
    conn.close()
    return row


# Alias for backward and cross-module compatibility
get_student_by_id = get_student_by_db_id



def get_student_by_student_id(student_id: str):
    conn = get_db_connection()
    row = conn.execute(
        "SELECT * FROM students WHERE TRIM(student_id) = TRIM(?) COLLATE NOCASE",
        (student_id.strip(),),
    ).fetchone()
    conn.close()
    return row


def get_student_by_name(full_name: str):
    conn = get_db_connection()
    row = conn.execute(
        "SELECT * FROM students WHERE TRIM(full_name) = TRIM(?) COLLATE NOCASE",
        (full_name.strip(),),
    ).fetchone()
    conn.close()
    return row


def generate_guest_id() -> str:
    """
    Generate a guaranteed unique guest ID like GST-2026-XXXX.
    Enables immediate guest/visitor enrollment without requiring institutional ID.
    """
    import random
    import string
    year = datetime.now().year
    conn = get_db_connection()
    while True:
        suffix = "".join(random.choices(string.digits, k=4))
        candidate = f"GST-{year}-{suffix}"
        row = conn.execute("SELECT id FROM students WHERE student_id = ? COLLATE NOCASE", (candidate,)).fetchone()
        if not row:
            conn.close()
            return candidate


def check_student_duplicate(full_name: str, student_id: str = "", exclude_id: int = None, is_guest: bool = False) -> tuple:
    """
    Check if a student or guest with the same student_id or full_name already exists in the database.
    Performs case-insensitive and whitespace-trimmed matching.
    Returns (is_duplicate: bool, error_message: str).
    """
    clean_id = (student_id or "").strip()
    clean_name = (full_name or "").strip()
    conn = get_db_connection()

    # 1. Check Student / Guest ID if provided
    if clean_id:
        query_id = "SELECT * FROM students WHERE TRIM(student_id) = ? COLLATE NOCASE"
        params_id = [clean_id]
        if exclude_id is not None:
            query_id += " AND id != ?"
            params_id.append(exclude_id)
        existing_id = conn.execute(query_id, params_id).fetchone()
        if existing_id:
            conn.close()
            user_label = "Guest" if is_guest else "Student"
            return True, f"{user_label} ID '{clean_id}' is already enrolled ({existing_id['full_name']})."

    # 2. Check Full Name
    # For generic walk-in names (e.g., 'Guest', 'Visitor'), allow multiple registrations
    generic_names = {"guest", "visitor", "walk-in", "walk-in guest", "external guest", "guest visitor", "scholar"}
    if is_guest and clean_name.lower() in generic_names:
        conn.close()
        return False, ""

    if clean_name:
        query_name = "SELECT * FROM students WHERE TRIM(full_name) = ? COLLATE NOCASE"
        params_name = [clean_name]
        if exclude_id is not None:
            query_name += " AND id != ?"
            params_name.append(exclude_id)
        existing_name = conn.execute(query_name, params_name).fetchone()
        conn.close()
        if existing_name:
            user_type = "Guest" if existing_name["program"] == "Guest" else "User"
            return True, f"{user_type} '{clean_name}' (ID: {existing_name['student_id']}) is already enrolled."

    conn.close()
    return False, ""


def update_student_status(db_id: int, status: str):
    conn = get_db_connection()
    conn.execute("UPDATE students SET status = ? WHERE id = ?", (status, db_id))
    conn.commit()
    conn.close()


def delete_student(db_id: int):
    """Delete a student and their attendance logs (FK constraint)."""
    conn = get_db_connection()
    conn.execute("DELETE FROM attendance_logs WHERE student_db_id = ?", (db_id,))
    conn.execute("DELETE FROM students WHERE id = ?", (db_id,))
    conn.commit()
    conn.close()


def count_students() -> int:
    conn = get_db_connection()
    n = conn.execute("SELECT COUNT(*) FROM students WHERE status = 'active'").fetchone()[0]
    conn.close()
    return n


# ══════════════════════════════════════════════════════════════════════════════
# Attendance CRUD
# ══════════════════════════════════════════════════════════════════════════════

def log_time_in(student_db_id: int, visit_purpose: str, node: str = "entry") -> int:
    """Create a new attendance record (Time In). Returns new record id."""
    now = datetime.now()
    conn = get_db_connection()
    c = conn.cursor()
    c.execute(
        """INSERT INTO attendance_logs (student_db_id, date, time_in, visit_purpose, node)
           VALUES (?, ?, ?, ?, ?)""",
        (student_db_id, now.strftime("%Y-%m-%d"), now.strftime("%H:%M:%S"),
         visit_purpose, node),
    )
    conn.commit()
    new_id = c.lastrowid
    conn.close()
    return new_id


def get_active_inside_session(student_db_id: int):
    """
    Check if the student has an active Time In record (time_in recorded, time_out IS NULL)
    from today or within the current open cycle.
    Returns the attendance log row if currently inside the facility, or None.
    """
    today_str = datetime.now().strftime("%Y-%m-%d")
    yesterday_str = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")
    conn = get_db_connection()
    row = conn.execute(
        """SELECT id, student_db_id, date, time_in, time_out, visit_purpose, node
           FROM attendance_logs
           WHERE student_db_id = ?
             AND time_out IS NULL
             AND (date = ? OR date = ?)
           ORDER BY id DESC LIMIT 1""",
        (student_db_id, today_str, yesterday_str),
    ).fetchone()
    conn.close()
    return row


def log_time_out(student_db_id: int) -> bool:
    """
    Update the open (time_out IS NULL) attendance record for the student.
    Returns True if an open inside session was found and updated.
    Returns False if the student was NOT captured during entrance.
    """
    open_session = get_active_inside_session(student_db_id)
    if not open_session:
        return False

    now_time = datetime.now().strftime("%H:%M:%S")
    conn = get_db_connection()
    c = conn.cursor()
    c.execute(
        """UPDATE attendance_logs
           SET time_out = ?
           WHERE id = ? AND time_out IS NULL""",
        (now_time, open_session["id"]),
    )
    conn.commit()
    updated = c.rowcount > 0
    conn.close()
    return updated


def get_attendance_logs(date_from: str = None, date_to: str = None,
                        program: str = None, purpose: str = None,
                        search: str = None, limit: int = 500):
    """Fetch filtered attendance logs joined with student info."""
    conn = get_db_connection()
    query = """
        SELECT al.id, s.full_name, s.student_id, s.program,
               al.date, al.time_in, al.time_out, al.visit_purpose, al.node
        FROM attendance_logs al
        JOIN students s ON al.student_db_id = s.id
        WHERE 1=1
    """
    params = []
    if date_from:
        query += " AND al.date >= ?"
        params.append(date_from)
    if date_to:
        query += " AND al.date <= ?"
        params.append(date_to)
    if program:
        query += " AND s.program = ?"
        params.append(program)
    if purpose:
        query += " AND al.visit_purpose = ?"
        params.append(purpose)
    if search:
        query += " AND (s.full_name LIKE ? OR s.student_id LIKE ?)"
        params.extend([f"%{search}%", f"%{search}%"])
    query += " ORDER BY al.id DESC LIMIT ?"
    params.append(limit)
    rows = conn.execute(query, params).fetchall()
    conn.close()
    return rows


def get_todays_visitor_count() -> int:
    today = datetime.now().strftime("%Y-%m-%d")
    conn = get_db_connection()
    n = conn.execute(
        "SELECT COUNT(*) FROM attendance_logs WHERE date = ?", (today,)
    ).fetchone()[0]
    conn.close()
    return n


def get_currently_inside_count() -> int:
    today = datetime.now().strftime("%Y-%m-%d")
    conn = get_db_connection()
    n = conn.execute(
        "SELECT COUNT(*) FROM attendance_logs WHERE date = ? AND time_out IS NULL",
        (today,),
    ).fetchone()[0]
    conn.close()
    return n


def get_hourly_traffic(date: str = None):
    if not date:
        date = datetime.now().strftime("%Y-%m-%d")
    conn = get_db_connection()
    rows = conn.execute(
        """SELECT strftime('%H', time_in) AS hour, COUNT(*) AS count
           FROM attendance_logs
           WHERE date = ?
           GROUP BY hour ORDER BY hour""",
        (date,),
    ).fetchall()
    conn.close()
    return rows


def get_purpose_breakdown(date_from: str = None, date_to: str = None):
    conn = get_db_connection()
    query = """
        SELECT visit_purpose, COUNT(*) AS count
        FROM attendance_logs
        WHERE visit_purpose IS NOT NULL
    """
    params = []
    if date_from:
        query += " AND date >= ?"
        params.append(date_from)
    if date_to:
        query += " AND date <= ?"
        params.append(date_to)
    query += " GROUP BY visit_purpose"
    rows = conn.execute(query, params).fetchall()
    conn.close()
    return rows


def get_department_breakdown(date_from: str = None, date_to: str = None):
    """
    Return all departments/programs and their visit counts in descending order (highest first).
    """
    conn = get_db_connection()
    query = """
        SELECT COALESCE(s.program, 'Unknown') AS department, COUNT(al.id) AS count
        FROM attendance_logs al
        LEFT JOIN students s ON al.student_db_id = s.id
        WHERE al.id IS NOT NULL
    """
    params = []
    if date_from:
        query += " AND al.date >= ?"
        params.append(date_from)
    if date_to:
        query += " AND al.date <= ?"
        params.append(date_to)
    query += " GROUP BY department ORDER BY count DESC"
    rows = conn.execute(query, params).fetchall()
    conn.close()
    return rows


def get_highest_visiting_department(date_from: str = None, date_to: str = None):
    """
    Return the department with the highest number of visits for the specified period.
    Returns dict: {"department": str, "count": int, "percentage": float, "total_visits": int}
    or None if no attendance records exist.
    """
    rows = get_department_breakdown(date_from=date_from, date_to=date_to)
    if not rows:
        return None
    total_visits = sum(r["count"] for r in rows)
    top = rows[0]
    pct = round((top["count"] / total_visits) * 100, 1) if total_visits > 0 else 0.0
    return {
        "department": top["department"],
        "count": top["count"],
        "percentage": pct,
        "total_visits": total_visits,
    }


def get_recent_logs(limit: int = 10):
    conn = get_db_connection()
    rows = conn.execute(
        """SELECT al.id, s.full_name, s.program, al.date, al.time_in,
                  al.time_out, al.visit_purpose
           FROM attendance_logs al
           JOIN students s ON al.student_db_id = s.id
           ORDER BY al.id DESC LIMIT ?""",
        (limit,),
    ).fetchall()
    conn.close()
    return rows


# ══════════════════════════════════════════════════════════════════════════════
# Security Alerts CRUD
# ══════════════════════════════════════════════════════════════════════════════

def log_alert(snapshot_path: str = None, confidence_score: float = None) -> int:
    conn = get_db_connection()
    c = conn.cursor()
    c.execute(
        """INSERT INTO security_alerts (snapshot_path, confidence_score)
           VALUES (?, ?)""",
        (snapshot_path, confidence_score),
    )
    conn.commit()
    new_id = c.lastrowid
    conn.close()
    return new_id


def get_alerts(resolved: int = None, limit: int = 200):
    conn = get_db_connection()
    query = "SELECT * FROM security_alerts WHERE 1=1"
    params = []
    if resolved is not None:
        query += " AND resolved = ?"
        params.append(resolved)
    query += " ORDER BY id DESC LIMIT ?"
    params.append(limit)
    rows = conn.execute(query, params).fetchall()
    conn.close()
    return rows


def resolve_alert(alert_id: int):
    conn = get_db_connection()
    conn.execute("UPDATE security_alerts SET resolved = 1 WHERE id = ?", (alert_id,))
    conn.commit()
    conn.close()


def resolve_all_alerts():
    conn = get_db_connection()
    conn.execute("UPDATE security_alerts SET resolved = 1 WHERE resolved = 0")
    conn.commit()
    conn.close()


def delete_alert(alert_id: int):
    """Delete a single alert and return its snapshot path for file deletion."""
    conn = get_db_connection()
    row = conn.execute("SELECT snapshot_path FROM security_alerts WHERE id = ?", (alert_id,)).fetchone()
    conn.execute("DELETE FROM security_alerts WHERE id = ?", (alert_id,))
    conn.commit()
    conn.close()
    return row["snapshot_path"] if row else None


def delete_all_resolved_alerts():
    """Delete all resolved alerts and return their snapshot paths for file deletion."""
    conn = get_db_connection()
    rows = conn.execute("SELECT snapshot_path FROM security_alerts WHERE resolved = 1 AND snapshot_path IS NOT NULL").fetchall()
    conn.execute("DELETE FROM security_alerts WHERE resolved = 1")
    conn.commit()
    conn.close()
    return [row["snapshot_path"] for row in rows]


def count_unresolved_alerts() -> int:
    conn = get_db_connection()
    n = conn.execute(
        "SELECT COUNT(*) FROM security_alerts WHERE resolved = 0"
    ).fetchone()[0]
    conn.close()
    return n


# ══════════════════════════════════════════════════════════════════════════════
# Admins CRUD
# ══════════════════════════════════════════════════════════════════════════════

def get_admin_by_username(username: str):
    conn = get_db_connection()
    row = conn.execute(
        "SELECT * FROM admins WHERE username = ?", (username,)
    ).fetchone()
    conn.close()
    return row


def create_admin(
    username: str,
    password_hash: str,
    security_question: str = "What is the official name of the CSUCC library building?",
    security_answer_hash: str = None,
    recovery_key_hash: str = None,
):
    conn = get_db_connection()
    conn.execute(
        """INSERT INTO admins (username, password_hash, security_question, security_answer_hash, recovery_key_hash)
           VALUES (?, ?, ?, ?, ?)""",
        (username, password_hash, security_question, security_answer_hash, recovery_key_hash),
    )
    conn.commit()
    conn.close()


def get_admin_by_id(admin_id: int):
    """Fetch an admin row by primary key."""
    conn = get_db_connection()
    row = conn.execute(
        "SELECT * FROM admins WHERE id = ?", (admin_id,)
    ).fetchone()
    conn.close()
    return row


def update_admin_password(admin_id: int, new_password_hash: str):
    """Update the password hash for the given admin ID."""
    conn = get_db_connection()
    conn.execute(
        "UPDATE admins SET password_hash = ? WHERE id = ?",
        (new_password_hash, admin_id),
    )
    conn.commit()
    conn.close()


def reset_admin_password_by_username(username: str, new_password_hash: str) -> bool:
    """Reset the password hash for an admin matching username."""
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute(
        "UPDATE admins SET password_hash = ? WHERE TRIM(username) = TRIM(?) COLLATE NOCASE",
        (new_password_hash, username.strip()),
    )
    affected = cur.rowcount
    conn.commit()
    conn.close()
    return affected > 0


def update_admin_recovery(
    admin_id: int,
    security_question: str,
    security_answer_hash: str,
    recovery_key_hash: str,
):
    """Update recovery question, answer hash, and recovery key hash for an admin."""
    conn = get_db_connection()
    conn.execute(
        """UPDATE admins
           SET security_question = ?, security_answer_hash = ?, recovery_key_hash = ?
           WHERE id = ?""",
        (security_question, security_answer_hash, recovery_key_hash, admin_id),
    )
    conn.commit()
    conn.close()
