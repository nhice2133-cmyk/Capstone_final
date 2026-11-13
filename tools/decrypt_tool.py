"""
SMART ENTRY — Biometric & Snapshot Image Decryption Tool
Caraga State University Cabadbaran Campus (CSUCC) - Athenaeum Library
---------------------------------------------------------------------
Allows administrators to decrypt authenticated AES-encrypted biometric face
datasets (.enc) and stranger surveillance snapshots (.enc) into viewable JPEG files.

Supports:
1. Export Decrypted Images to a Dedicated Folder (Safe & Recommended - keeps originals intact)
2. Decrypt In-Place (.enc -> .jpg directly in face_data/ and static/snapshots/)
3. Re-Encrypt In-Place (.jpg -> .enc to restore security-at-rest)
4. Decrypt a Specific File or Target Directory
"""

import os
import sys
import argparse
import subprocess
from pathlib import Path

# Ensure project root is in sys.path
PROJECT_ROOT = Path(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from config import Config
from recognition.image_crypto import (
    decrypt_image_bytes,
    encrypt_directory_files,
    encrypt_all_saved_images,
)

DEFAULT_EXPORT_DIR = PROJECT_ROOT / "decrypted_export"


def export_decrypted_images(dest_dir: Path = None) -> dict:
    """
    Decrypts all .enc files from face_data/ and static/snapshots/ into
    a designated export folder as standard viewable .jpg images.
    Leaves original .enc files untouched.
    """
    if dest_dir is None:
        dest_dir = DEFAULT_EXPORT_DIR
    dest_dir = Path(dest_dir)

    face_src = Path(Config.FACE_DATA_DIR)
    snap_src = Path(Config.ALERTS_SNAPSHOT_DIR)

    face_count = 0
    snap_count = 0

    print(f"\n[*] Exporting decrypted images to: {dest_dir}")
    os.makedirs(dest_dir, exist_ok=True)

    # 1. Decrypt face_data/
    if face_src.exists():
        for root, _, files in os.walk(face_src):
            rel = Path(root).relative_to(face_src)
            # Skip staging
            if "staging" in rel.parts:
                continue

            target_folder = dest_dir / "face_data" / rel
            for f in files:
                if f.lower().endswith(".enc"):
                    src_file = Path(root) / f
                    raw_jpg = decrypt_image_bytes(src_file)
                    if raw_jpg:
                        os.makedirs(target_folder, exist_ok=True)
                        out_name = f[:-4] + ".jpg"
                        out_file = target_folder / out_name
                        with open(out_file, "wb") as fp:
                            fp.write(raw_jpg)
                        face_count += 1

    # 2. Decrypt static/snapshots/
    if snap_src.exists():
        target_snap_folder = dest_dir / "snapshots"
        for root, _, files in os.walk(snap_src):
            for f in files:
                if f.lower().endswith(".enc"):
                    src_file = Path(root) / f
                    raw_jpg = decrypt_image_bytes(src_file)
                    if raw_jpg:
                        os.makedirs(target_snap_folder, exist_ok=True)
                        out_name = f[:-4] + ".jpg"
                        out_file = target_snap_folder / out_name
                        with open(out_file, "wb") as fp:
                            fp.write(raw_jpg)
                        snap_count += 1

    total = face_count + snap_count
    return {
        "success": True,
        "destination": str(dest_dir),
        "face_images": face_count,
        "snapshot_images": snap_count,
        "total": total,
    }


def decrypt_directory_in_place(directory_path: str) -> int:
    """
    Decodes all .enc files in directory_path to .jpg files and safely removes the .enc files.
    """
    if not os.path.exists(directory_path):
        return 0

    count = 0
    for root, _, files in os.walk(directory_path):
        for f in files:
            if f.lower().endswith(".enc"):
                src = os.path.join(root, f)
                dst = os.path.splitext(src)[0] + ".jpg"
                try:
                    raw_jpg = decrypt_image_bytes(src)
                    if raw_jpg and raw_jpg.startswith(b"\xff\xd8\xff"):
                        with open(dst, "wb") as fp:
                            fp.write(raw_jpg)
                        os.remove(src)
                        count += 1
                except Exception as e:
                    print(f"  [WARN] Failed to decrypt {src}: {e}")
    return count


def decrypt_in_place() -> dict:
    """
    Decodes all .enc files in-place inside face_data/ and static/snapshots/.
    """
    print("\n[*] Decrypting all files in-place (.enc -> .jpg)...")
    face_count = decrypt_directory_in_place(Config.FACE_DATA_DIR)
    snap_count = decrypt_directory_in_place(Config.ALERTS_SNAPSHOT_DIR)
    total = face_count + snap_count
    return {
        "success": True,
        "face_images": face_count,
        "snapshot_images": snap_count,
        "total": total,
    }


def decrypt_single_file(file_path: str, output_path: str = None) -> bool:
    """
    Decrypts a single .enc file and writes raw JPEG.
    """
    p = Path(file_path)
    if not p.exists():
        print(f"[ERROR] File not found: {file_path}")
        return False

    raw_jpg = decrypt_image_bytes(p)
    if not raw_jpg:
        print(f"[ERROR] Decryption returned empty payload or invalid cipher.")
        return False

    if output_path is None:
        if p.suffix.lower() == ".enc":
            output_path = p.with_suffix(".jpg")
        else:
            output_path = p.parent / (p.stem + "_decrypted.jpg")

    with open(output_path, "wb") as fp:
        fp.write(raw_jpg)

    print(f"[SUCCESS] Decrypted -> {output_path}")
    return True


def open_folder_in_explorer(folder_path: str):
    """Opens the specified directory in Windows File Explorer."""
    p = Path(folder_path)
    if not p.exists():
        os.makedirs(p, exist_ok=True)
    if sys.platform == "win32":
        os.startfile(str(p))


def interactive_menu():
    """Interactive command-line menu."""
    while True:
        print("\n" + "=" * 78)
        print("  CARAGA STATE UNIVERSITY CABADBARAN CAMPUS (CSUCC) - ATHENAEUM LIBRARY")
        print("  SMART ENTRY: Facial Biometric & Snapshot Image Decryption Tool")
        print("=" * 78)
        print()
        print("  [1] Export Decrypted Images to Folder (Safe & Recommended - keeps originals)")
        print("  [2] Decrypt In-Place (Converts .enc -> .jpg directly in face_data & snapshots)")
        print("  [3] Re-Encrypt In-Place (Converts .jpg -> .enc to restore security at rest)")
        print("  [4] Decrypt a Single Specific File (.enc)")
        print("  [5] Open Decrypted Export Folder in Windows Explorer")
        print("  [6] Exit")
        print()
        print("=" * 78)

        choice = input("Enter choice [1-6]: ").strip()

        if choice == "1":
            print("\nOption 1: Exporting decrypted images...")
            res = export_decrypted_images()
            print(f"\n[DONE] Successfully exported {res['total']} decrypted image(s)!")
            print(f"  • Student Biometrics: {res['face_images']}")
            print(f"  • Stranger Snapshots: {res['snapshot_images']}")
            print(f"  • Location: {res['destination']}")

            if res["total"] > 0:
                ask_open = input("\nOpen decrypted export folder in File Explorer? (Y/N): ").strip().lower()
                if ask_open in ("y", "yes"):
                    open_folder_in_explorer(res["destination"])
            else:
                print("  (Note: Currently 0 encrypted files found in face_data/ or static/snapshots/)")
            input("\nPress Enter to continue...")

        elif choice == "2":
            confirm = input("\n[WARNING] This will convert all .enc files to .jpg on disk. Proceed? (Y/N): ").strip().lower()
            if confirm in ("y", "yes"):
                res = decrypt_in_place()
                print(f"\n[DONE] Decrypted {res['total']} image(s) in-place.")
                print(f"  • Student Biometrics: {res['face_images']}")
                print(f"  • Stranger Snapshots: {res['snapshot_images']}")
            else:
                print("Operation cancelled.")
            input("\nPress Enter to continue...")

        elif choice == "3":
            print("\n[*] Re-encrypting all images in-place (.jpg -> .enc)...")
            res = encrypt_all_saved_images()
            print(f"\n[DONE] Re-encrypted {res['total']} image(s) in-place.")
            print(f"  • Student Biometrics: {res['encrypted_faces']}")
            print(f"  • Stranger Snapshots: {res['encrypted_snapshots']}")
            input("\nPress Enter to continue...")

        elif choice == "4":
            path_input = input("\nEnter full path to .enc file: ").strip().strip('"')
            if path_input:
                decrypt_single_file(path_input)
            input("\nPress Enter to continue...")

        elif choice == "5":
            open_folder_in_explorer(DEFAULT_EXPORT_DIR)

        elif choice == "6":
            print("\nExiting decryption tool. Goodbye!")
            break
        else:
            print("\n[!] Invalid selection! Please enter 1-6.")


def main():
    parser = argparse.ArgumentParser(description="SMART ENTRY Image Decryption Tool")
    parser.add_argument("--export", action="store_true", help="Export all decrypted images to decrypted_export/ folder")
    parser.add_argument("--inplace", action="store_true", help="Decrypt all files in-place (.enc -> .jpg)")
    parser.add_argument("--encrypt", action="store_true", help="Re-encrypt all files in-place (.jpg -> .enc)")
    parser.add_argument("--file", type=str, help="Path to single .enc file to decrypt")
    parser.add_argument("--dest", type=str, default=None, help="Destination directory for exported images")
    parser.add_argument("--open", action="store_true", help="Open export folder in File Explorer after exporting")

    args = parser.parse_args()

    if args.export:
        dest = Path(args.dest) if args.dest else DEFAULT_EXPORT_DIR
        res = export_decrypted_images(dest)
        print(f"[OK] Exported {res['total']} decrypted image(s) to: {res['destination']}")
        if args.open:
            open_folder_in_explorer(res["destination"])
        sys.exit(0)

    if args.inplace:
        res = decrypt_in_place()
        print(f"[OK] Decrypted {res['total']} image(s) in-place.")
        sys.exit(0)

    if args.encrypt:
        res = encrypt_all_saved_images()
        print(f"[OK] Re-encrypted {res['total']} image(s) in-place.")
        sys.exit(0)

    if args.file:
        ok = decrypt_single_file(args.file, args.dest)
        sys.exit(0 if ok else 1)

    # If no flags passed, run interactive menu
    interactive_menu()


if __name__ == "__main__":
    main()

