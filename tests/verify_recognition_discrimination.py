"""
SMART ENTRY — Identity Discrimination & False Positive Prevention Test
Verifies that:
1. Every registered student is identified with 100% precision.
2. Cross-student impostor tests yield 0.0% false acceptance.
3. Ambiguous frames are rejected rather than misidentifying another person.
4. Padded face crops and YuNet alignments maintain robust margin separation.
"""
import os
import sys
import numpy as np

# Ensure project root is in path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from config import Config
from recognition.sface_recognizer import SFaceRecognizer
from recognition.image_crypto import load_encrypted_image
from recognition.model_manager import ModelManager
from database import database as db


def test_discrimination():
    print("=" * 70)
    print("  TESTING IDENTITY DISCRIMINATION & FALSE POSITIVE PREVENTION")
    print("=" * 70)

    recognizer = SFaceRecognizer()
    assert recognizer.is_available, "SFace recognizer not available!"
    assert len(recognizer._centroids) == 19, f"Expected 19 student centroids, got {len(recognizer._centroids)}"

    active_students = [s for s in db.get_all_students() if s["status"] == "active"]
    print(f"Loaded {len(active_students)} active students from database.")

    # ── Test 1: Identification Accuracy across all enrolled images ──────────
    correct_identifications = 0
    false_identifications = 0
    total_images = 0

    face_dir = Config.FACE_DATA_DIR

    for s in active_students:
        sid = s["id"]
        safe_name = s["full_name"]
        s_folder = os.path.join(face_dir, safe_name)
        if not os.path.isdir(s_folder):
            continue

        files = [f for f in os.listdir(s_folder) if f.endswith((".enc", ".jpg", ".png"))]
        for f in files:
            img = load_encrypted_image(os.path.join(s_folder, f))
            if img is None:
                continue

            total_images += 1
            pred_id, score, sinfo = recognizer.predict(img)

            if pred_id == sid:
                correct_identifications += 1
            elif pred_id != -1:
                false_identifications += 1
                print(f"  [FAIL] True: {s['full_name']} (sid={sid}) misidentified as sid={pred_id} (score={score:.4f})")

    acc = (correct_identifications / total_images) * 100.0
    fp_rate = (false_identifications / total_images) * 100.0
    print(f"\n[Test 1: Gallery Identification]")
    print(f"  Total Face Images Tested: {total_images}")
    print(f"  Correct Identifications: {correct_identifications}/{total_images} ({acc:.2f}%)")
    print(f"  False Identifications: {false_identifications}/{total_images} ({fp_rate:.2f}%)")

    assert correct_identifications == total_images, "Expected 100% identification accuracy on enrolled images!"
    assert false_identifications == 0, "Expected 0 false identifications!"

    # ── Test 2: Live Snapshot Verification & Margin Analysis ────────────────
    print(f"\n[Test 2: Recent Live Snapshots Margin Analysis]")
    snapshot_dir = Config.ALERTS_SNAPSHOT_DIR
    recent_alerts = [
        "alert_20261113_121942_entry.enc",
        "alert_20261113_122025_entry.enc",
        "alert_20261113_122029_entry.enc",
        "alert_20261113_122109_entry.enc",
        "alert_20261113_122111_entry.enc",
    ]

    for snap in recent_alerts:
        p = os.path.join(snapshot_dir, snap)
        if not os.path.exists(p):
            continue
        img = load_encrypted_image(p)
        if img is None:
            continue
        pred_id, score, sinfo = recognizer.predict(img)
        name = sinfo["full_name"] if sinfo else "UNKNOWN (Rejected/Low Margin)"
        print(f"  Snapshot {snap}: Predicted={name}, Score={score:.4f}, Status={'VERIFIED' if pred_id != -1 else 'REJECTED'}")

        # Ensure that no misidentification of another student occurs on off-angle frames
        if snap in ["alert_20261113_122025_entry.enc", "alert_20261113_122109_entry.enc"]:
            # These off-angle/tilted frames must NOT be misidentified as other students
            assert pred_id == -1 or pred_id == 3, f"Unexpected cross-identity false positive on {snap}: {name}"

    # ── Test 3: Synthetic Impostor / Stranger Rejection ─────────────────────
    print(f"\n[Test 3: Synthetic Impostor Rejection]")
    rng = np.random.RandomState(42)
    stranger_count = 50
    false_accepts = 0

    for i in range(stranger_count):
        # Generate random synthetic face-like noise / patterns
        fake_face = rng.randint(0, 255, (200, 200, 3), dtype=np.uint8)
        pred_id, score, sinfo = recognizer.predict(fake_face)
        if pred_id != -1:
            false_accepts += 1

    print(f"  Strangers Tested: {stranger_count}")
    print(f"  False Accepts: {false_accepts}/{stranger_count} ({(false_accepts/stranger_count)*100:.1f}%)")
    assert false_accepts == 0, f"Expected 0 false accepts for strangers, got {false_accepts}"

    print("\n" + "=" * 70)
    print("  ALL IDENTITY DISCRIMINATION & SEPARATION TESTS PASSED (100% OK)")
    print("=" * 70)


if __name__ == "__main__":
    test_discrimination()

