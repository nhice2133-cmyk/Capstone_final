import sys
import os
import glob
import numpy as np

sys.path.insert(0, "C:/SmartEntry")
from recognition.image_crypto import load_encrypted_image
from recognition.face_detection import FaceDetector
from recognition.sface_recognizer import SFaceRecognizer
from recognition.model_manager import ModelManager
from database import database as db

rec = SFaceRecognizer()
students = db.get_all_students()
active_students = [s for s in students if s["status"] == "active"]

print(f"Testing recognition across all {len(active_students)} active students...")

total_tested = 0
total_correct = 0
confusion_errors = []

for s in active_students:
    sid = s["id"]
    name = s["full_name"]
    folder = os.path.join("C:/SmartEntry/face_data", name)
    if not os.path.isdir(folder):
        continue
    files = [f for f in os.listdir(folder) if f.endswith(".enc")]
    for f in files[:5]: # test 5 samples per student
        img = load_encrypted_image(os.path.join(folder, f))
        if img is None:
            continue
        pred_sid, score, sinfo = rec.predict(img)
        total_tested += 1
        if pred_sid == sid:
            total_correct += 1
        else:
            pred_name = sinfo["full_name"] if sinfo else "UNKNOWN"
            confusion_errors.append((name, pred_name, score))

print(f"Results: {total_correct}/{total_tested} correct ({total_correct/total_tested*100:.1f}%)")
if confusion_errors:
    print(f"Mismatches ({len(confusion_errors)}):")
    for orig, pred, sc in confusion_errors[:10]:
        print(f"  Expected {orig} -> Got {pred} (score={sc:.4f})")
else:
    print("Zero false positive confusions across all students!")

