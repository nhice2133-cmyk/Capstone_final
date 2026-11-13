"""
Test suite for tools/decrypt_tool.py
CSUCC Athenaeum SMART ENTRY System
"""
import os
import sys
import shutil
import numpy as np
import cv2
from pathlib import Path

PROJECT_ROOT = Path(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from config import Config
from recognition.image_crypto import save_encrypted_image, load_encrypted_image
from tools.decrypt_tool import (
    export_decrypted_images,
    decrypt_directory_in_place,
    decrypt_single_file,
    encrypt_all_saved_images,
)

def test_decryption_tool():
    print("=" * 70)
    print("  TESTING DECRYPTION ENGINE & BATCH INTEGRATION")
    print("=" * 70)

    # Setup dummy student in face_data
    test_student_dir = Path(Config.FACE_DATA_DIR) / "Test_Decryption_User"
    os.makedirs(test_student_dir, exist_ok=True)

    test_snap_dir = Path(Config.ALERTS_SNAPSHOT_DIR)
    os.makedirs(test_snap_dir, exist_ok=True)

    # Create dummy images
    dummy_img = np.zeros((120, 120, 3), dtype=np.uint8)
    dummy_img[:, :] = (100, 150, 200)

    enc_face = test_student_dir / "test_000.enc"
    enc_snap = test_snap_dir / "alert_test.enc"

    save_encrypted_image(str(enc_face), dummy_img)
    save_encrypted_image(str(enc_snap), dummy_img)

    assert enc_face.exists(), "Encrypted face file should exist"
    assert enc_snap.exists(), "Encrypted snapshot file should exist"
    print("\n[Step 1] Created sample encrypted .enc files in face_data and snapshots.")

    # 1. Test Export Mode
    export_target = PROJECT_ROOT / "temp_test_export"
    if export_target.exists():
        shutil.rmtree(export_target)

    res = export_decrypted_images(export_target)
    print(f"\n[Step 2] Exported decrypted images: {res}")
    assert res["success"] is True
    assert res["face_images"] >= 1
    assert res["snapshot_images"] >= 1

    # Verify exported file is valid JPEG
    exported_face = export_target / "face_data" / "Test_Decryption_User" / "test_000.jpg"
    assert exported_face.exists(), "Exported face JPEG should exist"
    with open(exported_face, "rb") as fp:
        header = fp.read(3)
    assert header == b"\xff\xd8\xff", "Exported file must be valid JPEG"
    print("  -> Exported JPEG verified: Valid JPEG magic header (FF D8 FF).")

    # Original .enc must still exist
    assert enc_face.exists(), "Original .enc file must remain untouched during export!"
    print("  -> Original .enc preserved untouched in face_data/.")

    # 2. Test Single File Decryption
    single_out = PROJECT_ROOT / "temp_single.jpg"
    if single_out.exists():
        single_out.unlink()
    ok = decrypt_single_file(str(enc_face), str(single_out))
    assert ok is True
    assert single_out.exists()
    print("\n[Step 3] Single file decryption verified.")
    if single_out.exists():
        single_out.unlink()

    # 3. Test In-Place Decryption
    print("\n[Step 4] Testing In-Place Decryption (.enc -> .jpg)...")
    dec_count = decrypt_directory_in_place(str(test_student_dir))
    assert dec_count >= 1
    jpg_face = test_student_dir / "test_000.jpg"
    assert jpg_face.exists(), "In-place converted .jpg should exist"
    assert not enc_face.exists(), "Original .enc should be removed after in-place decryption"
    print(f"  -> Converted {dec_count} file(s) in-place: .enc removed, .jpg created.")

    # 4. Test In-Place Re-Encryption
    print("\n[Step 5] Testing In-Place Re-Encryption (.jpg -> .enc)...")
    enc_count = encrypt_all_saved_images()
    assert enc_face.exists(), "Re-encrypted .enc should exist"
    assert not jpg_face.exists(), ".jpg should be removed after re-encryption"
    print(f"  -> Re-encrypted successfully: .jpg removed, .enc restored.")

    # 5. Clean up
    if test_student_dir.exists():
        shutil.rmtree(test_student_dir)
    if enc_snap.exists():
        enc_snap.unlink()
    if export_target.exists():
        shutil.rmtree(export_target)

    print("\n" + "=" * 70)
    print("  ALL DECRYPTION TOOL TESTS PASSED SUCCESSFULLY!")
    print("=" * 70)

if __name__ == "__main__":
    test_decryption_tool()

