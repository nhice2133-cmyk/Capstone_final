"""
SMART ENTRY — Flask Application Factory
Entry point for the application.

Run:
    python app.py
Access:
    Kiosk:   http://localhost:5000/kiosk
    Admin:   http://localhost:5000/admin   (login: admin / smart_entry_2026)
"""
import os
from datetime import timedelta
from flask import Flask, redirect, url_for
from flask_login import LoginManager
from flask_bcrypt import Bcrypt

from config import Config
from database.database import init_db, get_admin_by_username, create_admin
from routes.auth import auth_bp, AdminUser
from routes.dashboard import dashboard_bp
from routes.students import students_bp
from routes.attendance import attendance_bp
from routes.kiosk import kiosk_bp
from routes.models import models_bp
from routes.backup import backup_bp

bcrypt = Bcrypt()
login_manager = LoginManager()


def create_app():
    app = Flask(__name__, template_folder="templates", static_folder="static")
    app.config.from_object(Config)
    app.config["PERMANENT_SESSION_LIFETIME"] = timedelta(
        minutes=Config.SESSION_TIMEOUT_MINUTES
    )

    # ── Extensions ────────────────────────────────────────────────────────
    bcrypt.init_app(app)
    login_manager.init_app(app)
    login_manager.login_view = "auth.login"
    login_manager.login_message = "Please log in to access the admin panel."
    login_manager.login_message_category = "warning"

    # ── Blueprints ────────────────────────────────────────────────────────
    app.register_blueprint(auth_bp)
    app.register_blueprint(dashboard_bp)
    app.register_blueprint(students_bp)
    app.register_blueprint(attendance_bp)
    app.register_blueprint(kiosk_bp)
    app.register_blueprint(models_bp)
    app.register_blueprint(backup_bp)

    # ── Root redirect ─────────────────────────────────────────────────────
    @app.route("/")
    def index():
        return redirect(url_for("kiosk.kiosk_entry"))

    # ── Inject pending alert count into all templates ─────────────────────
    @app.context_processor
    def inject_alert_count():
        from flask_login import current_user
        if current_user.is_authenticated:
            from database.database import count_unresolved_alerts
            return {"pending_alerts_count": count_unresolved_alerts()}
        return {"pending_alerts_count": 0}

    return app


@login_manager.user_loader
def load_user(user_id):
    from database.database import get_db_connection
    conn = get_db_connection()
    row = conn.execute("SELECT * FROM admins WHERE id = ?", (user_id,)).fetchone()
    conn.close()
    if row:
        return AdminUser(row)
    return None


def _seed_default_admin(app):
    """Create a default admin account on first run if none exists, or ensure recovery hashes exist."""
    with app.app_context():
        from database.database import get_db_connection
        existing = get_admin_by_username("admin")
        rec_hash = bcrypt.generate_password_hash(Config.ADMIN_RECOVERY_KEY).decode("utf-8")
        ans_hash = bcrypt.generate_password_hash(Config.DEFAULT_SECURITY_ANSWER.lower()).decode("utf-8")

        if not existing:
            pw_hash = bcrypt.generate_password_hash("smart_entry_2026").decode("utf-8")
            create_admin(
                "admin",
                pw_hash,
                Config.DEFAULT_SECURITY_QUESTION,
                ans_hash,
                rec_hash,
            )
            print("[OK] Default admin created: username=admin  password=smart_entry_2026")
            print("[!]  Change the default password after first login!")
        else:
            # Ensure existing database has recovery key & security question hashes set
            conn = get_db_connection()
            row = conn.execute("SELECT * FROM admins WHERE username = 'admin'").fetchone()
            keys = row.keys() if hasattr(row, "keys") else []
            has_rec = ("recovery_key_hash" in keys and row["recovery_key_hash"])
            has_ans = ("security_answer_hash" in keys and row["security_answer_hash"])
            if not has_rec or not has_ans:
                conn.execute(
                    """UPDATE admins
                       SET security_question = COALESCE(security_question, ?),
                           security_answer_hash = COALESCE(security_answer_hash, ?),
                           recovery_key_hash = COALESCE(recovery_key_hash, ?)
                       WHERE username = 'admin'""",
                    (Config.DEFAULT_SECURITY_QUESTION, ans_hash, rec_hash),
                )
                conn.commit()
            conn.close()


if __name__ == "__main__":
    # ── Ensure required directories exist ────────────────────────────────
    os.makedirs(Config.FACE_DATA_DIR, exist_ok=True)
    os.makedirs(Config.ALERTS_SNAPSHOT_DIR, exist_ok=True)
    os.makedirs(os.path.join("recognition", "haarcascade"), exist_ok=True)

    # ── Initialise database ───────────────────────────────────────────────
    init_db()
    print("[OK] Database initialised.")

    # ── Biometric & snapshot encryption at rest ──────────────────────────
    try:
        from recognition.image_crypto import encrypt_all_saved_images
        crypto_res = encrypt_all_saved_images()
        if crypto_res.get("total", 0) > 0:
            print(f"[OK] Biometric encryption: Secured {crypto_res['total']} image(s) at rest.")
    except Exception as e:
        print(f"[WARN] Biometric encryption migration: {e}")

    app = create_app()
    _seed_default_admin(app)

    print("\n" + "=" * 60)
    print("  SMART ENTRY -- CSUCC Library Kiosk System")
    print("=" * 60)
    print(f"  Smart Entry Kiosk: http://localhost:5000/kiosk")
    print(f"  Admin Panel:       http://localhost:5000/admin")
    print(f"  Login:             admin / smart_entry_2026")
    print("=" * 60 + "\n")

    app.run(host="0.0.0.0", port=5000, debug=Config.DEBUG, threaded=True)
