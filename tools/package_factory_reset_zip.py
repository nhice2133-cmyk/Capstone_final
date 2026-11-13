"""
Package Factory Reset System into Desktop/SYSTEM_REORGANIZED_FINAL.zip
CSUCC Athenaeum SMART ENTRY System
"""
import os
import sys
import zipfile
import shutil
from pathlib import Path

PROJECT_ROOT = Path(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
ZIP_OUTPUT = Path("C:/Users/TECH ONLY/Desktop/SYSTEM_REORGANIZED_FINAL.zip")

EXCLUDE_DIRS = {
    ".git",
    "venv",
    ".venv",
    "__pycache__",
    "build",
    "dist",
    ".pytest_cache",
    ".idea",
    ".vscode",
}

EXCLUDE_EXTENSIONS = {
    ".pyc",
    ".pyo",
    ".tmp",
    ".log",
}

EXCLUDE_FILES = {
    "Thumbs.db",
    ".DS_Store",
}

def should_include(rel_path_str: str) -> bool:
    parts = Path(rel_path_str).parts
    for part in parts:
        if part in EXCLUDE_DIRS:
            return False
    
    filename = os.path.basename(rel_path_str)
    if filename in EXCLUDE_FILES:
        return False
    
    _, ext = os.path.splitext(filename)
    if ext.lower() in EXCLUDE_EXTENSIONS:
        return False
    
    # Don't include other zip archives or backups inside the zip
    if ext.lower() == ".zip" or ext.lower() == ".tar":
        return False

    # Do not include face images or stranger snapshots
    norm = rel_path_str.replace("\\", "/").lower()
    if norm.startswith("face_data/") and not norm.endswith("staging") and not norm.endswith(".gitkeep"):
        # Allow empty staging placeholder only
        if "staging" not in norm:
            return False
    if norm.startswith("static/snapshots/") and norm != "static/snapshots/":
        return False
        
    return True

def build_zip():
    print(f"[*] Packaging project from: {PROJECT_ROOT}")
    print(f"[*] Destination ZIP: {ZIP_OUTPUT}")

    # Temporary zip destination to prevent locking
    temp_zip = ZIP_OUTPUT.with_suffix(".tmp.zip")
    if temp_zip.exists():
        temp_zip.unlink()

    included_count = 0
    total_uncompressed_bytes = 0

    with zipfile.ZipFile(temp_zip, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=6) as zf:
        for root, dirs, files in os.walk(PROJECT_ROOT):
            # Prune excluded directories in-place
            dirs[:] = [d for d in dirs if d not in EXCLUDE_DIRS]
            
            rel_dir = os.path.relpath(root, PROJECT_ROOT)
            
            # Ensure empty directories like face_data/staging and static/snapshots exist
            if rel_dir != ".":
                norm_dir = rel_dir.replace("\\", "/") + "/"
                if norm_dir in ("face_data/", "face_data/staging/", "static/snapshots/", "recognition/models/"):
                    zf.writestr(norm_dir, "")

            for f in files:
                full_path = os.path.join(root, f)
                rel_path = os.path.relpath(full_path, PROJECT_ROOT)
                
                if should_include(rel_path):
                    norm_arcname = rel_path.replace("\\", "/")
                    zf.write(full_path, arcname=norm_arcname)
                    included_count += 1
                    total_uncompressed_bytes += os.path.getsize(full_path)

    # Atomic rename
    if ZIP_OUTPUT.exists():
        ZIP_OUTPUT.unlink()
    temp_zip.rename(ZIP_OUTPUT)

    zip_size_mb = os.path.getsize(ZIP_OUTPUT) / (1024 * 1024)
    raw_size_mb = total_uncompressed_bytes / (1024 * 1024)

    print(f"[SUCCESS] Packaged {included_count} files into {ZIP_OUTPUT.name}")
    print(f"  Uncompressed Size: {raw_size_mb:.2f} MB")
    print(f"  Compressed ZIP Size: {zip_size_mb:.2f} MB")

if __name__ == "__main__":
    build_zip()
