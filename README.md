# SMART ENTRY: A Face Recognition-Based Attendance and Security Surveillance Kiosk System
### Caraga State University – Cabadbaran Campus (CSUCC) | Athenaeum Learning Commons
**Bachelor of Science in Information Technology (BSIT) Capstone Project (2026)**

---

## 🏛️ System Overview

**SMART ENTRY** is an offline biometric attendance and real-time security surveillance kiosk system designed specifically for the **Athenaeum Learning Commons** at **Caraga State University Cabadbaran Campus (CSUCC)**. The platform provides automated, contactless student and visitor logging, stranger security alerting, and comprehensive library usage analytics while operating **100% offline** without any cloud or internet dependencies.

### Key Highlights
- **100% Offline Resilience:** Bundled local Google Fonts (56 WOFF2 files), standalone Chart.js 4.4, local SQLite database, and ONNX neural network weights ensure complete autonomy from external networks.
- **Deep Biometric Pipeline:** Integrates OpenCV **YuNet** for 5-point affine landmark face detection & normalization paired with **SFace** (MobileFaceNet) 128-dimensional deep feature embeddings.
- **Touchless Entry Kiosk (`/kiosk`):** Live webcam feed with sub-second face identification, visit purpose logging, and automated stranger snapshot capture.
- **Administrative Control Panel (`/admin`):** Comprehensive analytics dashboard, student record management, auto-capture biometric enrollment, guest registration, model retraining, and security audit logs.
- **Two-Step Master Key Recovery:** Secure administrative account restoration utilizing an institutional Master Recovery Key (`CSUCC-ATHENAEUM-RESET-2026`) with dynamic SVG password visibility toggles.
- **Automated Deployment & Maintenance:** Standalone compiled installer (`Smart_Entry_Setup.exe`), batch launcher (`smart_entry_launcher.bat`), and hot backup/restore utility (`smart_entry_backup.bat`).

---

## 📂 Reorganized Folder Structure

```
SmartEntry_Reorganized/
├── app.py                         # Main Flask application entry point & factory
├── config.py                      # Global configuration parameters & constants
├── requirements.txt               # Pinned Python package dependencies
├── reset_admin.py                 # Emergency admin credential recovery utility
├── setup.bat                      # One-click Windows setup runner
├── setup_wizard.py                # Graphical deployment wizard (Tkinter)
├── Smart_Entry_Setup.exe          # Compiled standalone deployment executable
├── smart_entry_launcher.bat       # Interactive system launcher & control console
├── smart_entry_backup.bat         # Automated backup & restore batch script
├── tray_app.py                    # Windows system tray monitor & background runner
├── NEW_PC_SETUP_GUIDE.txt         # Offline deployment walkthrough for technicians
├── README.md                      # Comprehensive project documentation (this file)
│
├── backups/                       # System snapshot archives & recovery points
│   └── README.txt                 # Archive directory usage policy
│
├── database/                      # Data storage layer & SQLite schemas
│   ├── database.py                # Schema initialization, ORM helpers & query logic
│   └── smart_entry.db             # Primary SQLite relational database
│
├── docs/                          # Academic documentation & capstone defense materials
│   ├── ARCHITECTURE.md            # Technical system architecture & offline specifications
│   ├── backup_manifest.json       # Archive validation & hash checksums
│   ├── build_manuscript.py        # Manuscript compilation automation script
│   ├── generate_diagrams.py       # Architecture & flow diagram generator
│   ├── NEW_PC_SETUP_GUIDE.txt     # Formatted technician deployment guide
│   ├── SMART_ENTRY_MANUSCRIPT.docx# Official capstone manuscript (MS Word)
│   ├── SMART_ENTRY_MANUSCRIPT.md  # Complete capstone manuscript (Markdown)
│   ├── BSIT_Final_Defense_Forms/  # Oral defense routing & institutional evaluation forms
│   └── diagrams/                  # System architecture, use case, and DFD diagrams
│
├── face_data/                     # Enrolled student facial image datasets
│   └── <student_db_id>/           # 20-sample cropped facial training sets per student
│
├── logo/                          # Institutional & application branding assets
│   ├── smart_entry.ico            # Windows executable & taskbar icon
│   └── smart_entry_logo.png       # High-resolution application brandmark
│
├── recognition/                   # Computer vision & deep learning engine
│   ├── face_detection.py          # Haar Cascade & YuNet detection wrappers
│   ├── face_recognition.py        # High-level recognition coordinator & matcher
│   ├── model_manager.py           # Model metadata, versioning & threshold controls
│   ├── sface_recognizer.py        # SFace 128-D embedding extraction & cosine similarity
│   ├── training.py                # Student centroid training & embedding generator
│   └── models/                    # Pre-trained ONNX deep learning weights
│       ├── face_detection_yunet_2023mar.onnx
│       ├── face_recognition_sface_2021dec.onnx
│       └── sface_embeddings.npz   # Compressed numpy array of trained student centroids
│
├── routes/                        # Flask Blueprints (Modular request handlers)
│   ├── admin.py                   # System administration & maintenance routes
│   ├── analytics.py               # Statistical aggregation & JSON endpoints
│   ├── attendance.py              # Log inspection, filtering, and CSV export
│   ├── auth.py                    # Admin authentication, session & Master Key recovery
│   ├── dashboard.py               # Administrative summary stats & live metrics
│   ├── kiosk.py                   # Real-time kiosk stream & biometric verification API
│   ├── models.py                  # Model retraining & threshold calibration
│   └── students.py                # Student enrollment, search, and record management
│
├── static/                        # Offline static web assets
│   ├── css/                       # Modular CSS stylesheets (admin.css, kiosk.css, main.css)
│   ├── fonts/                     # 56 bundled local WOFF2 font files (Zero CDN reliance)
│   ├── images/                    # Campus facade, Athenaeum photos, CSU seals
│   ├── js/                        # Local JavaScript (dashboard.js, enrollment.js, kiosk.js)
│   │   └── chart.umd.min.js       # Bundled offline Chart.js v4.4 library
│   └── snapshots/                 # Automatic captures of unrecognized/stranger faces
│
├── templates/                     # Jinja2 HTML templates
│   ├── base.html                  # Core layout with navigation & offline asset links
│   ├── admin/                     # Administrative views (dashboard, analytics, logs, models)
│   ├── auth/                      # Authentication views (login, forgot_password, change_password)
│   └── kiosk/                     # Full-screen touchless kiosk interface
│
├── tests/                         # Automated verification & test suites
│   ├── test_forgot_password.py    # Unit & integration suite for Master Key recovery & SVG toggles
│   ├── test_guest_enrollment.py   # Test suite for guest visitor registration
│   └── test_system_e2e.py         # Playwright end-to-end full offline verification suite
│
└── tools/                         # Maintenance scripts & data utilities
    ├── backup_restore.py          # Database & biometric archive manager
    ├── create_shortcut.py         # Automated Windows desktop shortcut creator
    └── seed_500_lfw.py            # Large-scale synthetic testing dataset generator
```

---

## ⚡ Quick Start & Installation

### Option 1: One-Click Setup Wizard (Recommended)
1. Double-click `setup.bat` or run `Smart_Entry_Setup.exe`.
2. Follow the graphical setup wizard:
   - Validates Python 3.10+ installation and pip.
   - Automatically installs all dependencies from `requirements.txt`.
   - Initializes the SQLite database and default admin accounts.
   - Detects connected USB webcams.
   - Places a **SMART ENTRY Kiosk** shortcut directly on your Windows Desktop.

### Option 2: Console Launcher
Double-click `smart_entry_launcher.bat` to open the interactive system menu:
```
======================================================================
  SMART ENTRY: CSUCC ATHENAEUM BIOMETRIC KIOSK SYSTEM
======================================================================
  [1] Start Full System (Flask Server + Browser)
  [2] Launch Entry Kiosk Only (Dedicated Window)
  [3] Open Admin Panel Only
  [4] Run System Tray App
  [5] Create Desktop Shortcuts
  [6] Backup System Database & Biometrics
  [7] Run Automated Test Suite
  [8] Emergency Admin Password Reset
  [0] Open Graphical Setup Wizard
======================================================================
```

### Option 3: Manual Command Line
```powershell
# 1. Install dependencies
pip install -r requirements.txt

# 2. Initialize database & seed models
python -c "from database.database import init_db; init_db()"

# 3. Start the Flask application
python app.py
```
Access the system in your web browser:
- **Admin Dashboard:** `http://localhost:5000/admin`
- **Entry Kiosk:** `http://localhost:5000/kiosk`
- **Login Portal:** `http://localhost:5000/login`

---

## 🔐 System Credentials & Security Configuration

| Credential Type | Parameter | Default Value | Notes |
|-----------------|-----------|---------------|-------|
| **Admin Login** | Username | `admin` | Primary administrative account |
| **Admin Login** | Password | `smart_entry_2026` | Bcrypt-hashed password |
| **Recovery** | Master Key | `CSUCC-ATHENAEUM-RESET-2026` | Used at `/admin/forgot-password` |
| **Emergency Tool** | Console Reset | Run `python reset_admin.py` | Restores default admin instantly |

### Security Safeguards
- **Zero Cloud Leakage:** All biometric embeddings, face photos, and attendance logs reside strictly on local storage (`database/smart_entry.db` and `face_data/`).
- **Dynamic Password Toggles:** Custom SVG vector eye icons (Open Eye ↔ Slashed Eye) provide clear, responsive password visibility toggling without layout jumping.
- **Two-Step Account Recovery:** Password resets require prior authorization with the institutional Master Recovery Key before allowing new password entry.
- **Session Protections:** 30-minute inactivity session timeouts and CSRF-protected form handling.

---

## 🧪 Testing & Verification

The reorganized project includes comprehensive automated test suites to guarantee offline integrity and operational reliability:

```powershell
# Run Master Recovery Key & SVG Toggle verification
python tests/test_forgot_password.py

# Run Full System & Playwright End-to-End browser tests (Offline verification)
python tests/test_system_e2e.py
```

### Verification Highlights:
- ✅ **Offline Integrity:** Verified 0 network calls to CDNs; bundled Chart.js and fonts load 100% locally.
- ✅ **Authentication:** Validated login, logout, bad login rejection, and session persistence.
- ✅ **Master Key Recovery:** Validated 2-step verification, rejection of invalid keys, and password updates.
- ✅ **Kiosk Recognition:** Validated camera stream, sub-second YuNet alignment, and SFace feature extraction.
- ✅ **Admin Controls:** Validated student enrollment, guest registration, analytics charts, and model retraining.

---

## 🎓 Academic Citations & Project Details

- **Capstone Project:** SMART ENTRY: A Face Recognition-Based Attendance and Security Surveillance Kiosk System For The CSUCC Library
- **Institution:** Caraga State University – Cabadbaran Campus (CSUCC)
- **College:** College of Engineering and Information Technology (CEIT)
- **Department:** Department of Information Technology
- **Location:** CSUCC Athenaeum Learning Commons (Library)
- **Year:** 2026

*Refer to the `docs/` folder for the full capstone manuscript (`SMART_ENTRY_MANUSCRIPT.docx`), technical architecture document (`ARCHITECTURE.md`), and defense forms.*
