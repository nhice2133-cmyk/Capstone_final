"""
SMART ENTRY — Auth Routes
Handles admin login and logout using Flask-Login + Flask-Bcrypt.
"""
from flask import Blueprint, render_template, redirect, url_for, request, flash
from flask_login import login_user, logout_user, login_required, current_user, UserMixin
from database.database import get_admin_by_username

auth_bp = Blueprint("auth", __name__)


class AdminUser(UserMixin):
    """Minimal Flask-Login User wrapper for admin accounts."""

    def __init__(self, row):
        self.id = row["id"]
        self.username = row["username"]


@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    from app import bcrypt  # imported here to avoid circular imports
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        admin_row = get_admin_by_username(username)
        if admin_row and bcrypt.check_password_hash(admin_row["password_hash"], password):
            login_user(AdminUser(admin_row), remember=False)
            return redirect(url_for("dashboard.home"))
        flash("Invalid username or password.", "error")
    return render_template("auth/login.html")


@auth_bp.route("/logout")
@login_required
def logout():
    logout_user()
    flash("You have been logged out.", "info")
    return redirect(url_for("auth.login"))


@auth_bp.route("/change-password", methods=["GET", "POST"])
@auth_bp.route("/admin/change-password", methods=["GET", "POST"])
@login_required
def change_password():
    from app import bcrypt  # imported here to avoid circular imports
    from database.database import get_admin_by_id, update_admin_password

    if request.method == "POST":
        current_pw = request.form.get("current_password", "")
        new_pw = request.form.get("new_password", "")
        confirm_pw = request.form.get("confirm_password", "")

        admin_row = get_admin_by_id(current_user.id)

        if not admin_row:
            flash("Admin account not found.", "error")
            return redirect(url_for("auth.change_password"))

        if not bcrypt.check_password_hash(admin_row["password_hash"], current_pw):
            flash("Current password is incorrect.", "error")
            return redirect(url_for("auth.change_password"))

        if len(new_pw) < 6:
            flash("New password must be at least 6 characters.", "error")
            return redirect(url_for("auth.change_password"))

        if new_pw != confirm_pw:
            flash("New passwords do not match.", "error")
            return redirect(url_for("auth.change_password"))

        if current_pw == new_pw:
            flash("New password must be different from the current one.", "error")
            return redirect(url_for("auth.change_password"))

        new_hash = bcrypt.generate_password_hash(new_pw).decode("utf-8")
        update_admin_password(current_user.id, new_hash)
        flash("Password changed successfully!", "success")
        return redirect(url_for("dashboard.home"))

    return render_template("admin/change_password.html")


def _verify_recovery_key(admin_row, recovery_key: str) -> bool:
    """Validate master recovery key against config or hashed database record."""
    from app import bcrypt  # imported here to avoid circular imports
    from config import Config

    if not recovery_key or not admin_row:
        return False

    clean_input = recovery_key.replace(" ", "").replace("-", "").upper()
    clean_config = Config.ADMIN_RECOVERY_KEY.replace(" ", "").replace("-", "").upper()

    if clean_input == clean_config:
        return True

    row_keys = admin_row.keys() if hasattr(admin_row, "keys") else []
    rec_hash = admin_row["recovery_key_hash"] if "recovery_key_hash" in row_keys else None
    if rec_hash:
        try:
            if bcrypt.check_password_hash(rec_hash, recovery_key):
                return True
        except Exception:
            pass

    return False


@auth_bp.route("/forgot-password", methods=["GET", "POST"])
@auth_bp.route("/admin/forgot-password", methods=["GET", "POST"])
def forgot_password():
    """
    Offline password recovery for administrator accounts.
    Two-step flow: Strictly requires valid Master Recovery Key before unlocking password fields.
    """
    from flask import jsonify
    from app import bcrypt  # imported here to avoid circular imports
    from database.database import get_admin_by_username, update_admin_password

    if current_user.is_authenticated:
        return redirect(url_for("dashboard.home"))

    if request.method == "POST":
        # Handle AJAX verification request
        action = request.form.get("action", "") or (request.json.get("action") if request.is_json else "")
        if action == "verify_key":
            if request.is_json:
                username = (request.json.get("username") or "admin").strip()
                recovery_key = (request.json.get("recovery_key") or "").strip()
            else:
                username = request.form.get("username", "admin").strip()
                recovery_key = request.form.get("recovery_key", "").strip()

            admin_row = get_admin_by_username(username)
            if not admin_row:
                return jsonify({"success": False, "message": f"Administrator account '{username}' was not found."})

            if not _verify_recovery_key(admin_row, recovery_key):
                return jsonify({"success": False, "message": "Invalid Master Recovery Key. Authorization failed."})

            return jsonify({
                "success": True,
                "message": "Master Recovery Key verified successfully! You may now enter your new password.",
                "username": username,
            })

        # Standard form submission (supports Step 1 and Step 2)
        step = str(request.form.get("step", "1")).strip()
        username = request.form.get("username", "admin").strip()
        recovery_key = request.form.get("recovery_key", "").strip()

        admin_row = get_admin_by_username(username)
        if not admin_row:
            flash(f"Administrator account '{username}' was not found.", "error")
            return render_template("auth/forgot_password.html", step=1, username=username)

        if not _verify_recovery_key(admin_row, recovery_key):
            flash("Invalid Master Recovery Key. Authorization failed.", "error")
            return render_template("auth/forgot_password.html", step=1, username=username)

        # If user submitted Step 1 or new_password is not yet provided
        new_password = request.form.get("new_password", "")
        confirm_password = request.form.get("confirm_password", "")

        if step == "1" or not new_password:
            flash("Master Recovery Key verified! Please enter your new security password below.", "info")
            return render_template("auth/forgot_password.html", step=2, username=username, recovery_key=recovery_key)

        # Step 2: Validate new password inputs
        if len(new_password) < 6:
            flash("New security password must be at least 6 characters long.", "error")
            return render_template("auth/forgot_password.html", step=2, username=username, recovery_key=recovery_key)

        if new_password != confirm_password:
            flash("New passwords do not match. Please re-enter both fields.", "error")
            return render_template("auth/forgot_password.html", step=2, username=username, recovery_key=recovery_key)

        # Authorized: update password hash in database
        new_hash = bcrypt.generate_password_hash(new_password).decode("utf-8")
        update_admin_password(admin_row["id"], new_hash)
        flash("Password successfully reset! Please sign in with your new credentials.", "success")
        return redirect(url_for("auth.login"))

    return render_template("auth/forgot_password.html", step=1, username="admin")
