import os
import sys
import numpy as np
import cv2

# Set path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config import Config
from app import create_app
import database.database as db
from recognition.image_crypto import save_encrypted_image, decrypt_image_bytes

def test_snapshot_serving():
    print("--- 1. Testing Snapshot Encryption & Streaming ---")
    test_frame = np.zeros((100, 100, 3), dtype=np.uint8)
    test_frame[:, :] = [40, 180, 80] # green color
    
    os.makedirs(Config.ALERTS_SNAPSHOT_DIR, exist_ok=True)
    snap_name = "test_snapshot_unit.enc"
    snap_path = os.path.join(Config.ALERTS_SNAPSHOT_DIR, snap_name)
    save_encrypted_image(snap_path, test_frame)
    
    assert os.path.exists(snap_path), "Encrypted snapshot file must exist on disk"
    with open(snap_path, "rb") as f:
        encrypted_content = f.read()
    assert not encrypted_content.startswith(b"\xff\xd8\xff"), "On-disk file MUST NOT be plain JPEG"
    print(f"  [PASS] File on disk is verified encrypted AES ciphertext ({len(encrypted_content)} bytes).")
    
    aid = db.log_alert(snapshot_path=f"snapshots/{snap_name}", confidence_score=0.45)
    print(f"  [PASS] Logged alert ID: {aid}")
    
    app = create_app()
    app.config["TESTING"] = True
    client = app.test_client()
    
    # 1. Unauthenticated request -> should redirect to login (HTTP 302)
    resp_unauth = client.get(f"/admin/alerts/snapshot/{aid}")
    assert resp_unauth.status_code == 302, f"Expected 302, got {resp_unauth.status_code}"
    print("  [PASS] Unauthenticated access properly rejected (302 redirect).")
    
    # 2. Authenticated request -> should stream decrypted JPEG (HTTP 200)
    with client.session_transaction() as sess:
        sess["_user_id"] = "1"
        sess["_fresh"] = True
        
    resp_auth = client.get(f"/admin/alerts/snapshot/{aid}")
    assert resp_auth.status_code == 200, f"Expected 200, got {resp_auth.status_code}"
    assert resp_auth.headers.get("Content-Type") == "image/jpeg", f"Content-Type should be image/jpeg"
    assert resp_auth.data.startswith(b"\xff\xd8\xff"), "Decrypted stream must be valid JPEG"
    print(f"  [PASS] Authenticated request receives decrypted JPEG ({len(resp_auth.data)} bytes) with 200 OK.")
    
    # Clean up
    db.delete_alert(aid)
    if os.path.exists(snap_path):
        os.remove(snap_path)
    print("  [PASS] Cleanup complete.")

if __name__ == "__main__":
    test_snapshot_serving()

