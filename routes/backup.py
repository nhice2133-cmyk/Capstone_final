"""
SMART ENTRY — System Backup & Disaster Recovery Blueprint
Enables library administrators to independently create, download, and restore:
1. System Core & Logs (Attendance logs, security alerts, alert snapshots, admin settings)
2. Enrolled Students & Face Biometrics (Patron profiles, face_data/ images, SFace embeddings)
3. Full System Snapshots (Combined complete disaster recovery)
"""

import os
from flask import (
    Blueprint,
    render_template,
    request,
    redirect,
    url_for,
    flash,
    send_file,
    jsonify
)
from flask_login import login_required
from tools.backup_restore import (
    get_system_manifest,
    create_system_backup,
    restore_system_backup,
    list_backups,
    delete_backup,
    BACKUPS_DIR
)

backup_bp = Blueprint("backup", __name__, url_prefix="/admin/backup")


@backup_bp.route("", methods=["GET"])
@login_required
def backup_dashboard():
    """Renders the Backup & Disaster Recovery Management dashboard."""
    manifest = get_system_manifest()
    backups = list_backups()
    
    # Categorize counts for dashboard pills
    counts = {
        "all": len(backups),
        "system": len([b for b in backups if b.get("backup_type") == "system"]),
        "biometrics": len([b for b in backups if b.get("backup_type") == "biometrics"]),
        "full": len([b for b in backups if b.get("backup_type") == "full"]),
    }
    
    return render_template(
        "admin/backup_restore.html",
        manifest=manifest,
        backups=backups,
        counts=counts
    )


@backup_bp.route("/create", methods=["POST"])
@login_required
def create_backup_action():
    """Creates a local backup archive for the specified category."""
    backup_type = request.form.get("backup_type", "system").strip().lower()
    if backup_type not in ["system", "biometrics", "full"]:
        backup_type = "system"

    description = request.form.get("description", "").strip()
    try:
        path = create_system_backup(description=description or None, backup_type=backup_type)
        filename = os.path.basename(path)
        
        type_labels = {
            "system": "System Core & Logs",
            "biometrics": "Enrolled Students & Biometrics",
            "full": "Full System Archive"
        }
        label = type_labels.get(backup_type, "Backup")
        flash(f"{label} created successfully: {filename}", "success")
    except Exception as e:
        flash(f"Failed to create backup: {str(e)}", "danger")
        
    return redirect(url_for("backup.backup_dashboard"))


@backup_bp.route("/download-current", methods=["GET"])
@login_required
def download_current_backup():
    """Generates a fresh backup archive for the selected category and streams download."""
    backup_type = request.args.get("type", "system").strip().lower()
    if backup_type not in ["system", "biometrics", "full"]:
        backup_type = "system"

    type_labels = {
        "system": "System Logs",
        "biometrics": "Students Biometrics",
        "full": "Full System"
    }
    label = type_labels.get(backup_type, "Backup")

    try:
        path = create_system_backup(
            description=f"Direct Download ({label})",
            backup_type=backup_type
        )
        filename = os.path.basename(path)
        return send_file(
            path,
            as_attachment=True,
            download_name=filename,
            mimetype="application/zip"
        )
    except Exception as e:
        flash(f"Could not generate {label} download: {str(e)}", "danger")
        return redirect(url_for("backup.backup_dashboard"))


@backup_bp.route("/download/<filename>", methods=["GET"])
@login_required
def download_existing_backup(filename):
    """Downloads an existing local backup archive from backups/."""
    safe_name = os.path.basename(filename)
    target_path = os.path.join(BACKUPS_DIR, safe_name)
    if os.path.exists(target_path) and os.path.isfile(target_path):
        return send_file(
            target_path,
            as_attachment=True,
            download_name=safe_name,
            mimetype="application/zip"
        )
    flash("The requested backup archive was not found.", "warning")
    return redirect(url_for("backup.backup_dashboard"))


@backup_bp.route("/restore", methods=["POST"])
@login_required
def restore_backup_action():
    """
    Restores data from an uploaded ZIP archive or an existing local snapshot.
    Automatically detects whether the archive is a System backup, Biometrics backup, or Full backup.
    """
    force_type = request.form.get("restore_type")
    
    # 1. Check if a file was uploaded
    uploaded_file = request.files.get("backup_file")
    if uploaded_file and uploaded_file.filename:
        filename = os.path.basename(uploaded_file.filename)
        if not filename.lower().endswith(".zip"):
            flash("Please upload a valid .zip backup archive.", "danger")
            return redirect(url_for("backup.backup_dashboard"))

        temp_target = os.path.join(BACKUPS_DIR, f"upload_{filename}")
        uploaded_file.save(temp_target)
        try:
            success, message = restore_system_backup(
                temp_target, 
                create_safety_snapshot=True, 
                force_type=force_type
            )
            if success:
                flash(message, "success")
            else:
                flash(message, "danger")
        finally:
            if os.path.exists(temp_target):
                try:
                    os.remove(temp_target)
                except Exception:
                    pass
        return redirect(url_for("backup.backup_dashboard"))

    # 2. Check if an existing local snapshot filename was selected
    selected_name = request.form.get("backup_filename")
    if selected_name:
        safe_name = os.path.basename(selected_name)
        target_path = os.path.join(BACKUPS_DIR, safe_name)
        if not os.path.exists(target_path):
            flash("Selected local backup file does not exist.", "danger")
            return redirect(url_for("backup.backup_dashboard"))

        success, message = restore_system_backup(
            target_path, 
            create_safety_snapshot=True, 
            force_type=force_type
        )
        if success:
            flash(message, "success")
        else:
            flash(message, "danger")
        return redirect(url_for("backup.backup_dashboard"))

    flash("No backup file was uploaded or selected for restoration.", "warning")
    return redirect(url_for("backup.backup_dashboard"))


@backup_bp.route("/delete/<filename>", methods=["POST"])
@login_required
def delete_backup_action(filename):
    """Deletes a local backup archive."""
    safe_name = os.path.basename(filename)
    if delete_backup(safe_name):
        flash(f"Backup archive '{safe_name}' was deleted.", "info")
    else:
        flash(f"Could not delete backup archive '{safe_name}'.", "danger")
    return redirect(url_for("backup.backup_dashboard"))
