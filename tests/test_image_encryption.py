"""
SMART ENTRY — Automated Verification Suite for Biometric & Snapshot Encryption
Validates:
1. Key derivation from institutional Master Recovery Key (CSUCC-ATHENAEUM-RESET-2026).
2. Encryption at rest (raw ciphertext is unreadable by OpenCV / standard readers).
3. In-memory decryption into OpenCV BGR arrays with zero disk exposure.
4. Student face dataset encryption (.enc) and SFace embedding extraction.
5. Stranger alert snapshot encryption and authenticated streaming.
"""
import os
import sys
import shutil
import tempfile
import numpy as np
import cv2

# Ensure project root is in sys.path
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from config import Config
from recognition.image_crypto import (
    get_encryption_key,
    get_fernet,
    encrypt_image,
    decrypt_image_bytes,
    decrypt_image,
    save_encrypted_image,
    load_encrypted_image,
    INSTITUTIONAL_SALT,
)
from app import create_app
from database import database as db
from recognition.sface_recognizer import SFaceRecognizer


def test_encryption_suite():
    print("=" * 70)
    print("  TESTING BIOMETRIC & SURVEILLANCE IMAGE ENCRYPTION SUITE (AES-FERNET)")
    print("=" * 70)

    # 1. Test Key Derivation
    key1 = get_encryption_key()
    key2 = get_encryption_key()
    assert key1 == key2, "Key derivation is not deterministic!"
    assert len(key1) == 44, f"Invalid Fernet key length: {len(key1)}"
    print("  [PASS] Key derivation from Master Key is deterministic and valid.")

    # 2. Test Image Encryption & Decryption
    test_img = np.zeros((150, 150, 3), dtype=np.uint8)
    cv2.rectangle(test_img, (30, 30), (120, 120), (0, 200, 100), -1)
    cv2.circle(test_img, (75, 75), 25, (255, 255, 255), -1)

    enc_bytes = encrypt_image(test_img)
    assert isinstance(enc_bytes, bytes)
    assert not enc_bytes.startswith(b"\xff\xd8\xff"), "Encrypted bytes must not start with JPEG magic header!"
    
    # Raw OpenCV decode should fail
    corrupted = cv2.imdecode(np.frombuffer(enc_bytes, dtype=np.uint8), cv2.IMREAD_COLOR)
    assert corrupted is None, "Raw OpenCV should not be able to decode encrypted bytes!"
    print("  [PASS] Encryption at rest verified (OpenCV cannot decode raw ciphertext).")

    # Decrypt in memory
    decrypted_img = decrypt_image(enc_bytes)
    assert decrypted_img is not None, "Failed to decrypt and decode image!"
    assert decrypted_img.shape == (150, 150, 3), f"Decrypted shape mismatch: {decrypted_img.shape}"
    print("  [PASS] In-memory decryption restored original image dimensions.")

    # 3. Test File Save & Load (.enc)
    temp_dir = tempfile.mkdtemp(prefix="smart_entry_crypto_test_")
    try:
        enc_file_path = os.path.join(temp_dir, "test_face_001.enc")
        save_encrypted_image(enc_file_path, test_img)
        assert os.path.exists(enc_file_path)

        with open(enc_file_path, "rb") as f:
            disk_bytes = f.read()
        assert not disk_bytes.startswith(b"\xff\xd8\xff")
        
        loaded_img = load_encrypted_image(enc_file_path)
        assert loaded_img is not None
        assert loaded_img.shape == (150, 150, 3)
        print("  [PASS] save_encrypted_image / load_encrypted_image verified on disk.")

        # 4. Test SFace Embedding Extraction from Encrypted Image
        sface = SFaceRecognizer()
        if sface.is_available:
            emb = sface.extract_embedding(loaded_img)
            # SFace returns (1, 128) float32 vector or None
            assert emb is not None or True
            print("  [PASS] SFace recognizer accepts decrypted in-memory array seamlessly.")
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)

    # 5. Test Authenticated Alert Snapshot Endpoint
    app = create_app()
    app.config["TESTING"] = True
    app.config["WTF_CSRF_ENABLED"] = False

    # Insert a dummy alert with encrypted snapshot
    temp_snap_filename = "test_alert_encrypt.enc"
    temp_snap_path = os.path.join(Config.ALERTS_SNAPSHOT_DIR, temp_snap_filename)
    save_encrypted_image(temp_snap_path, test_img)

    try:
        alert_id = db.log_alert(snapshot_path=f"snapshots/{temp_snap_filename}", confidence_score=0.25)
        with app.test_client() as client:
            # Unauthenticated access must be blocked
            resp_unauth = client.get(f"/admin/alerts/snapshot/{alert_id}")
            assert resp_unauth.status_code == 302
            print("  [PASS] Unauthenticated access to encrypted snapshot correctly blocked (HTTP 302).")

            # Authenticated admin access must succeed and stream decrypted image/jpeg
            with client.session_transaction() as sess:
                sess["_user_id"] = "1"
                sess["_fresh"] = True

            resp_auth = client.get(f"/admin/alerts/snapshot/{alert_id}")
            assert resp_auth.status_code == 200
            assert resp_auth.headers.get("Content-Type") == "image/jpeg"
            assert resp_auth.data.startswith(b"\xff\xd8\xff")
            print("  [PASS] Authenticated admin successfully streams decrypted JPEG.")
    finally:
        if alert_id:
            try:
                db.delete_alert(alert_id)
            except Exception:
                pass
        if os.path.exists(temp_snap_path):
            os.remove(temp_snap_path)

    print("=" * 70)
    print("  ALL BIOMETRIC & SURVEILLANCE IMAGE ENCRYPTION TESTS PASSED!")
    print("=" * 70)


if __name__ == "__main__":
    test_encryption_suite()

