# SMART ENTRY: A Face Recognition-Based Attendance and Security Surveillance Kiosk System For The CSUCC Library

---

## Quick Start

### 1. Prerequisites
- **Python 3.10 or higher**
- **USB Webcam (1080p recommended)** facing the library entrance portal
- Standard Desktop PC (Intel Core i3/i5 or AMD equivalent)
- Windows 10/11 (tested) or Linux

### 2. Install Dependencies

```bash
pip install -r requirements.txt
```

> **Important:** `opencv-contrib-python==4.10.0.84` is required for OpenCV's native SFace (`cv2.FaceRecognizerSF`) and YuNet (`cv2.FaceDetectorYN`) deep learning modules.

### 3. Run the Application

Double-click `smart_entry_launcher.bat` or run:
```bash
python app.py
```
python app.py
```

The server starts at: `http://localhost:5000`

---

## Access URLs

| URL | Description |
|-----|-------------|
| `http://localhost:5000/kiosk` | Entry Kiosk (full-screen, open in a dedicated browser window) |
| `` | Exit Monitor (passive departure logging) |
| `http://localhost:5000/admin` | Admin Dashboard |
| `http://localhost:5000/login` | Admin Login |

**Default Admin Credentials:**
- Username: `admin`
- Password: `smart_entry_2026`

> Change the default password after first login!

---

## Project Structure

```
smart_entry/
├── app.py                    # Flask app factory & entry point
├── config.py                 # All configurable parameters
├── requirements.txt          # Python dependencies
├── README.md                 # This file
│
├── database/
│   ├── database.py           # Schema creation & all CRUD helpers
│   └── smart_entry.db        # SQLite database (auto-created on first run)
│
├── recognition/
│   ├── face_detection.py     # Haar Cascade & face cropping wrapper
│   ├── face_recognition.py   # OpenCV SFace deep embeddings recognizer wrapper
│   ├── sface_recognizer.py   # MobileFaceNet 128-D embedding extractor
│   ├── model_manager.py      # Versioning, metadata & threshold manager
│   ├── training.py           # SFace embeddings generator
│   └── models/
│       ├── face_recognition_sface_2021dec.onnx
│       ├── face_detection_yunet_2023mar.onnx
│       └── sface_embeddings.npz
│
├── routes/
│   ├── auth.py               # Admin login / logout
│   ├── students.py           # Student enrollment & management
│   ├── attendance.py         # Attendance logs & CSV export & analytics
│   ├── dashboard.py          # Admin home & live stats
│   └── kiosk.py              # Kiosk stream, recognition API, alerts
│
├── templates/
│   ├── base.html
│   ├── auth/login.html
│   ├── kiosk/kiosk.html      # Full-screen kiosk UI
│   └── admin/                # All admin panel pages
│
├── static/
│   ├── css/main.css, kiosk.css, admin.css
│   ├── js/kiosk.js, enrollment.js, dashboard.js
│   └── snapshots/            # Stranger alert snapshots (auto-created)
│
└── face_data/                # Enrolled face images (auto-created)
    └── <student_db_id>/
        ├── img_000.jpg
        └── img_001.jpg …
```

---

## Configuration (`config.py`)

| Parameter | Default | Description |
|-----------|---------|-------------|
| `ENTRY_CAMERA_INDEX` | `0` | USB index of the Entry webcam |
| `EXIT_CAMERA_INDEX` | `1` | USB index of the Exit webcam |
| `RECOGNITION_THRESHOLD` | `0.363` | SFace cosine similarity threshold (higher = stricter) |
| `ENROLLMENT_IMAGE_COUNT` | `20` | Face images captured per enrollment |
| `ALERT_COOLDOWN_SECONDS` | `10` | Seconds between repeated stranger alerts |
| `SESSION_TIMEOUT_MINUTES` | `30` | Admin session expiry |

---

## Enrollment Workflow

1. Log in to the Admin Panel at `/admin`
2. Navigate to **Enroll Student**
3. **Step 1:** Enter student Full Name, Student ID, and Program
4. **Step 2:** Click **Start Auto-Capture** — the system captures 20 face images automatically
5. **Step 3:** SFace 128-D feature embeddings and student centroids are updated automatically

---

## System Workflow

### Entry Kiosk
1. Webcam streams continuously
2. Every ~2 seconds a frame is sent to the recognition API
3. If face detected → aligned with YuNet / cropped → SFace generates 128-D embedding vector
4. Cosine similarity compared against registered student centroids
5. If recognized (similarity >= 0.363) → student info displayed → Visit Purpose menu shown
6. Student selects purpose → Time In logged to SQLite
7. If unknown (similarity < 0.363) → Stranger alert logged + snapshot saved

### Exit Monitor
1. Webcam streams continuously (passive)
2. If recognized → Time Out logged automatically (no student interaction needed)

---

## Security Notes

- Admin passwords stored using `bcrypt` hashing
- No biometric data is transmitted externally — all data stays on local SQLite
- Stranger snapshots stored locally at `static/snapshots/`
- Session expires after 30 minutes of inactivity

---

## Technology Stack

| Component | Technology |
|-----------|-----------|
| Face Detection | OpenCV Haar Cascade Classifier & YuNet |
| Face Recognition | OpenCV SFace (MobileFaceNet 128-D Deep Feature Embeddings) |
| Backend | Python 3.11 + Flask |
| Database | SQLite (via sqlite3) |
| Auth | Flask-Login + Flask-Bcrypt |
| Frontend | HTML5 + CSS3 + Vanilla JavaScript |
| Charts | Chart.js 4.4 |
| Webcam | EMEET S600 4K Streaming Webcam (or any USB webcam) |

---

## For the Capstone Manuscript

**Project Title:** SMART ENTRY: A Face Recognition-Based Attendance and Security Surveillance Kiosk System For The CSUCC Library

**Institution:** Caraga State University – Cabadbaran Campus (CSUCC)

**Department:** Department of Information Technology (CEIT)

**Algorithms:**
- Face Detection & Alignment: YuNet 5-Point Affine Landmark Normalization & Haar Cascade
- Face Recognition: OpenCV SFace Deep Feature Embeddings (Cosine Similarity Metric $\ge 0.363$)

**Target Location:** CSUCC Library (Athenaeum Learning Commons)

---

*Developed as a BSIT Undergraduate Capstone Project, CSUCC, 2026.*
