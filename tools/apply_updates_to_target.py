"""
Apply all latest SMART ENTRY upgrades, security features, and tools
to a target directory (e.g. D:\Capstone_final-main or C:\SmartEntry)
WITHOUT overwriting the target's database (smart_entry.db) or face_data.
"""
import os
import sys
import shutil

SOURCE_DIR = r"c:\Users\TECH ONLY\Desktop\Capstone_Project-main"

ROOT_FILES = [
    "app.py",
    "config.py",
    "requirements.txt",
    "README.md",
    "NEW_PC_SETUP_GUIDE.txt",
    "smart_entry_launcher.bat",
    "smart_entry_backup.bat",
    "decrypt_files.bat",
    "tray_app.py",
    "reset_admin.py",
    "setup_wizard.py",
    "setup.bat",
]

SUBDIRS = [
    "recognition",
    "routes",
    "static",
    "templates",
    "tools",
    "logo",
    "tests",
]

def apply_updates(target_dir: str):
    print("=" * 70)
    print(f"APPLYING SYSTEM UPDATES TO: {target_dir}")
    print("=" * 70)

    if not os.path.exists(target_dir):
        raise FileNotFoundError(f"Target directory does not exist: {target_dir}")

    # Check that target database exists
    target_db = os.path.join(target_dir, "database", "smart_entry.db")
    if os.path.exists(target_db):
        print(f"[PRESERVED] Target database exists ({os.path.getsize(target_db)} bytes). It will NOT be overwritten.")
    else:
        print(f"[NOTICE] Target database does not exist. It will be initialized cleanly.")

    # 1. Copy root files
    print("\n[1] Updating root files...")
    for fname in ROOT_FILES:
        src = os.path.join(SOURCE_DIR, fname)
        dst = os.path.join(target_dir, fname)
        if os.path.exists(src):
            shutil.copy2(src, dst)
            print(f"  -> Updated {fname}")

    # 2. Update database/database.py ONLY (do NOT touch smart_entry.db!)
    print("\n[2] Updating database engine code...")
    src_db_py = os.path.join(SOURCE_DIR, "database", "database.py")
    dst_db_py = os.path.join(target_dir, "database", "database.py")
    os.makedirs(os.path.join(target_dir, "database"), exist_ok=True)
    shutil.copy2(src_db_py, dst_db_py)
    print("  -> Updated database/database.py")

    # 3. Copy subdirectories (excluding pycache, git, etc.)
    print("\n[3] Updating subdirectories (routes, templates, static, recognition, tools)...")
    for sdir in SUBDIRS:
        src_sub = os.path.join(SOURCE_DIR, sdir)
        dst_sub = os.path.join(target_dir, sdir)
        if not os.path.exists(src_sub):
            continue

        for root, dirs, files in os.walk(src_sub):
            dirs[:] = [d for d in dirs if d not in ("__pycache__", ".git", ".pytest_cache")]
            rel = os.path.relpath(root, src_sub)
            target_path = os.path.join(dst_sub, rel) if rel != "." else dst_sub
            os.makedirs(target_path, exist_ok=True)

            for f in files:
                if f.endswith((".pyc", ".pyo", ".tmp")):
                    continue
                src_f = os.path.join(root, f)
                dst_f = os.path.join(target_path, f)
                shutil.copy2(src_f, dst_f)
        print(f"  -> Updated {sdir}/")

    print("\n[4] Running database migration & schema check...")
    # Add target_dir to sys.path and run init_db
    sys.path.insert(0, target_dir)
    os.chdir(target_dir)

    import database.database as db
    db.init_db()
    print("  -> Target database initialized / verified compatible.")

    print("\n[5] Encrypting face images & snapshots at rest (AES-128-CBC + HMAC-SHA256)...")
    from recognition.image_crypto import encrypt_all_saved_images
    res = encrypt_all_saved_images()
    print(f"  -> Encryption result: {res}")

    print("\n[6] Retraining / updating SFace biometric feature embeddings...")
    from recognition.sface_recognizer import SFaceRecognizer
    rec = SFaceRecognizer()
    emb_res = rec.update_all_embeddings()
    print(f"  -> SFace embedding generation result: {emb_res}")

    print("\n" + "=" * 70)
    print(f"SUCCESS: System successfully updated in {target_dir}!")
    print("=" * 70)

if __name__ == "__main__":
    target = sys.argv[1] if len(sys.argv) > 1 else r"D:\Capstone_final-main"
    apply_updates(target)
