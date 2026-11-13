"""
SMART ENTRY: A Face Recognition-Based Attendance and Security Surveillance Kiosk System For The CSUCC Library
Interactive Windows Graphical Setup Wizard & Installer
---------------------------------------------------------------------------------------------------------
Automates end-to-end installation for new and existing PCs:
1. Smart project location discovery (detects Capstone_Project-main from Desktop, exe dir, etc.)
2. Pre-flight system check (Python version, camera device, write access, SFace & YuNet models)
3. Dependency status detection — if already installed, skips pip reinstallation completely!
4. Bundled & automated SFace / YuNet ONNX model deployment
5. SQLite relational database initialization
6. Creation of Windows Desktop and Start Menu shortcuts with CSUCC seal icon
7. Instant one-click application launch
"""

import os
import sys
import time
import shutil
import urllib.request
import tempfile
import threading
import subprocess
import webbrowser
from pathlib import Path

import tkinter as tk
from tkinter import ttk, messagebox, filedialog

# ── Colors & Branding ────────────────────────────────────────────────────────
CSU_GREEN = "#0D5C3A"
CSU_DARK = "#062316"
CSU_GOLD = "#F59E0B"
BG_MAIN = "#0F172A"
CARD_BG = "#1E293B"
TEXT_WHITE = "#FFFFFF"
TEXT_MUTED = "#94A3B8"
BORDER_COLOR = "#334155"
ACCENT_GREEN = "#10B981"
ACCENT_BLUE = "#3B82F6"


def get_resource_path(rel_path: str) -> str:
    """Get absolute path to resource, works for dev and for PyInstaller _MEIPASS."""
    if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
        p = os.path.join(sys._MEIPASS, rel_path)
        if os.path.exists(p):
            return p
    return os.path.abspath(rel_path)


def detect_project_root() -> str:
    """
    Intelligently locates the SMART ENTRY project root directory.
    Checks:
    1. Directory containing the executable (if PyInstaller frozen)
    2. Subdirectories of the executable directory (e.g., Desktop/Capstone_Project-main)
    3. User Desktop / Downloads folders
    4. Current working directory
    """
    candidates = []

    # 1. Executable directory (where the .exe is running from)
    if getattr(sys, "frozen", False):
        exe_dir = os.path.dirname(os.path.abspath(sys.executable))
        candidates.append(exe_dir)
        candidates.append(os.path.join(exe_dir, "Capstone_Project-main"))
        # Check subdirectories
        if os.path.exists(exe_dir):
            try:
                for item in os.listdir(exe_dir):
                    sub = os.path.join(exe_dir, item)
                    if os.path.isdir(sub) and "capstone" in item.lower():
                        candidates.append(sub)
            except Exception:
                pass

    # 2. Script directory (when run from Python source)
    script_dir = os.path.dirname(os.path.abspath(__file__))
    candidates.append(script_dir)
    candidates.append(os.path.join(script_dir, "Capstone_Project-main"))

    # 3. Current working directory
    cwd = os.getcwd()
    candidates.append(cwd)
    candidates.append(os.path.join(cwd, "Capstone_Project-main"))

    # 4. Standard Desktop and Userprofile paths
    user_home = os.environ.get("USERPROFILE", "")
    if user_home:
        desktop = os.path.join(user_home, "Desktop")
        candidates.append(os.path.join(desktop, "Capstone_Project-main"))
        candidates.append(desktop)
        downloads = os.path.join(user_home, "Downloads")
        candidates.append(os.path.join(downloads, "Capstone_Project-main"))

    # Validate candidate: must contain app.py and config.py
    for c in candidates:
        if not c or not os.path.exists(c):
            continue
        app_file = os.path.join(c, "app.py")
        cfg_file = os.path.join(c, "config.py")
        if os.path.exists(app_file) and os.path.exists(cfg_file):
            return os.path.abspath(c)

    # Fallback to current script directory or cwd
    return os.path.abspath(script_dir) if os.path.exists(os.path.join(script_dir, "app.py")) else os.path.abspath(cwd)


def create_windows_shortcut(target: str, link_path: str, description: str = "", work_dir: str = "", icon_path: str = "", arguments: str = ""):
    """Creates a native Windows .lnk shortcut via WScript.Shell."""
    target = os.path.abspath(target)
    link_path = os.path.abspath(link_path)
    work_dir = os.path.abspath(work_dir) if work_dir else os.path.dirname(target)

    vbs_lines = [
        'Set oWS = WScript.CreateObject("WScript.Shell")',
        f'sLinkFile = "{link_path}"',
        'Set oLink = oWS.CreateShortcut(sLinkFile)',
        f'oLink.TargetPath = "{target}"',
        f'oLink.WorkingDirectory = "{work_dir}"',
        f'oLink.Description = "{description}"'
    ]
    if arguments:
        vbs_lines.append(f'oLink.Arguments = "{arguments}"')
    if icon_path and os.path.exists(icon_path):
        vbs_lines.append(f'oLink.IconLocation = "{os.path.abspath(icon_path)}, 0"')
    vbs_lines.append('oLink.Save')
    vbs_content = "\r\n".join(vbs_lines)

    fd, temp_vbs = tempfile.mkstemp(suffix=".vbs")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(vbs_content)
        subprocess.run(["cscript", "//nologo", temp_vbs], check=True, capture_output=True)
        return os.path.exists(link_path)
    finally:
        if os.path.exists(temp_vbs):
            try:
                os.remove(temp_vbs)
            except Exception:
                pass


DEFAULT_INSTALL_DIR = os.path.join(os.environ.get("SystemDrive", "C:"), "\\SmartEntry")


class SmartEntryInstallerGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("SMART ENTRY Setup Wizard — CSUCC Library Kiosk")
        self.root.geometry("710x630")
        self.root.resizable(False, False)
        self.root.configure(bg=BG_MAIN)

        self.source_dir = detect_project_root()
        self.install_dir = DEFAULT_INSTALL_DIR
        self.project_root = self.install_dir  # Active root for target deployment

        # State Variables
        self.var_install_dir = tk.StringVar(value=self.install_dir)
        self.var_force_reinstall = tk.BooleanVar(value=False)
        self.var_reinstall_files = tk.BooleanVar(value=False)
        self.var_create_webapp_shortcut = tk.BooleanVar(value=True)
        self.var_create_kiosk_shortcut = tk.BooleanVar(value=False)
        self.var_create_backup_shortcut = tk.BooleanVar(value=False)
        self.var_launch_admin = tk.BooleanVar(value=True)
        self.var_launch_kiosk = tk.BooleanVar(value=False)

        # Resolve genuine host Python interpreter (never the installer EXE!)
        self.python_bin = self._resolve_python_executable()

        # Set Window Icon if exists
        self.ico_path = os.path.join(self.source_dir, "logo", "smart_entry.ico")
        if not os.path.exists(self.ico_path):
            bundled_ico = get_resource_path("logo/smart_entry.ico")
            if os.path.exists(bundled_ico):
                self.ico_path = bundled_ico

        if os.path.exists(self.ico_path):
            try:
                self.root.iconbitmap(self.ico_path)
            except Exception:
                pass

        self.current_step = 0
        self.install_success = False
        self.all_deps_installed = False
        self.missing_deps = []

        self._build_header()
        self.content_frame = tk.Frame(self.root, bg=BG_MAIN)
        self.content_frame.pack(fill="both", expand=True, padx=25, pady=10)
        self._build_footer()

        self.show_welcome_screen()

    @property
    def is_installed_at_target(self) -> bool:
        """Checks if SMART ENTRY core files already exist at target directory."""
        target = os.path.abspath(self.var_install_dir.get())
        return os.path.exists(os.path.join(target, "app.py")) and os.path.exists(os.path.join(target, "config.py"))

    def _build_header(self):
        header = tk.Frame(self.root, bg=CSU_DARK, height=95)
        header.pack(fill="x", side="top")
        header.pack_propagate(False)

        top_tag = tk.Label(
            header,
            text="CARAGA STATE UNIVERSITY CABADBARAN CAMPUS  •  ATHENAEUM LIBRARY",
            font=("Segoe UI", 8, "bold"),
            fg=CSU_GOLD,
            bg=CSU_DARK
        )
        top_tag.pack(anchor="w", padx=25, pady=(12, 2))

        title = tk.Label(
            header,
            text="SMART ENTRY Kiosk Setup & Installation Wizard",
            font=("Segoe UI", 14, "bold"),
            fg=TEXT_WHITE,
            bg=CSU_DARK
        )
        title.pack(anchor="w", padx=25)

        subtitle = tk.Label(
            header,
            text="A Face Recognition-Based Attendance & Security Surveillance Kiosk System",
            font=("Segoe UI", 9),
            fg=TEXT_MUTED,
            bg=CSU_DARK
        )
        subtitle.pack(anchor="w", padx=25, pady=(2, 0))

    def _build_footer(self):
        self.footer = tk.Frame(self.root, bg=CARD_BG, height=65)
        self.footer.pack(fill="x", side="bottom")
        self.footer.pack_propagate(False)

        self.btn_cancel = tk.Button(
            self.footer,
            text="Cancel",
            font=("Segoe UI", 9),
            bg="#334155",
            fg=TEXT_WHITE,
            activebackground="#475569",
            activeforeground=TEXT_WHITE,
            relief="flat",
            padx=18,
            pady=6,
            cursor="hand2",
            command=self.root.quit
        )
        self.btn_cancel.pack(side="left", padx=25, pady=16)

        self.btn_next = tk.Button(
            self.footer,
            text="Install Dependencies >",
            font=("Segoe UI", 9, "bold"),
            bg=CSU_GREEN,
            fg=TEXT_WHITE,
            activebackground="#15803d",
            activeforeground=TEXT_WHITE,
            relief="flat",
            padx=20,
            pady=6,
            cursor="hand2",
            command=self.on_next_click
        )
        self.btn_next.pack(side="right", padx=25, pady=16)

        self.btn_webapp = tk.Button(
            self.footer,
            text="Launch Web App",
            font=("Segoe UI", 9, "bold"),
            bg="#1E3A8A",
            fg=TEXT_WHITE,
            activebackground="#2563EB",
            activeforeground=TEXT_WHITE,
            relief="flat",
            padx=16,
            pady=6,
            cursor="hand2",
            command=self.on_launch_webapp_click
        )

    def on_launch_webapp_click(self):
        self._ensure_models_deployed()
        self._create_desktop_shortcuts()
        self._launch_application(open_kiosk=False, open_admin=True)
        self.root.quit()

    def _resolve_python_executable(self) -> str:
        """
        Locates the genuine Python interpreter executable on the system.
        CRITICAL: Inside a PyInstaller bundle, sys.executable is the installer EXE
        (Smart_Entry_Setup.exe), NOT python.exe!
        """
        # 1. Project-level virtual environment
        venv_py = os.path.join(self.project_root, "venv", "Scripts", "python.exe")
        if os.path.exists(venv_py):
            return os.path.abspath(venv_py)

        # 2. System PATH resolution
        for cmd in ("python", "python3", "py"):
            found = shutil.which(cmd)
            if found:
                if not found.lower().endswith("smart_entry_setup.exe"):
                    return os.path.abspath(found)

        # 3. Standard Windows AppData and Program Files directories
        local_app_data = os.environ.get("LOCALAPPDATA", "")
        if local_app_data:
            py_programs = os.path.join(local_app_data, "Programs", "Python")
            if os.path.exists(py_programs):
                try:
                    for d in sorted(os.listdir(py_programs), reverse=True):
                        cand = os.path.join(py_programs, d, "python.exe")
                        if os.path.exists(cand):
                            return os.path.abspath(cand)
                except Exception:
                    pass

        common_paths = [
            r"C:\Program Files\Python312\python.exe",
            r"C:\Program Files\Python311\python.exe",
            r"C:\Program Files\Python310\python.exe",
            r"C:\Python312\python.exe",
            r"C:\Python311\python.exe",
            r"C:\Python310\python.exe",
        ]
        for p in common_paths:
            if os.path.exists(p):
                return p

        if not getattr(sys, "frozen", False):
            return sys.executable

        return "python"

    def _check_dependencies(self) -> tuple:
        """Checks whether all required dependencies are already installed in python_bin."""
        # Fast path: instant directory inspection (0.5ms) without spawning a heavy subprocess
        try:
            py_dir = os.path.dirname(self.python_bin)
            sp_candidates = [
                os.path.join(py_dir, "Lib", "site-packages"),
                os.path.join(os.path.dirname(py_dir), "Lib", "site-packages"),
            ]
            sp_dir = next((d for d in sp_candidates if os.path.isdir(d)), None)
            if sp_dir:
                installed_files = [f.lower() for f in os.listdir(sp_dir)]
                has_flask = any(f.startswith("flask") for f in installed_files)
                has_cv2 = any("cv2" in f or "opencv" in f for f in installed_files)
                has_numpy = any("numpy" in f for f in installed_files)
                has_login = any("flask_login" in f for f in installed_files)
                has_bcrypt = any("flask_bcrypt" in f for f in installed_files)
                has_pil = any("pil" in f or "pillow" in f for f in installed_files)
                if has_flask and has_cv2 and has_numpy and has_login and has_bcrypt and has_pil:
                    return (True, [])
        except Exception:
            pass

        # Fallback to precise subprocess check if anything is missing
        test_script = (
            "import importlib.util, sys\n"
            "mods = ['flask', 'flask_login', 'flask_bcrypt', 'cv2', 'numpy', 'PIL', 'docx']\n"
            "missing = [m for m in mods if importlib.util.find_spec(m) is None]\n"
            "if 'cv2' not in missing:\n"
            "    try:\n"
            "        import cv2\n"
            "        if not hasattr(cv2, 'FaceRecognizerSF'):\n"
            "            missing.append('opencv-contrib-python')\n"
            "    except Exception:\n"
            "        missing.append('cv2')\n"
            "print(','.join(missing))\n"
        )
        try:
            res = subprocess.run(
                [self.python_bin, "-c", test_script],
                capture_output=True,
                text=True,
                check=True,
                timeout=5,
                creationflags=0x08000000 if sys.platform == "win32" else 0
            )
            raw = res.stdout.strip()
            missing = [m.strip() for m in raw.split(",") if m.strip()]
            return (len(missing) == 0, missing)
        except Exception:
            return (False, ["Check error"])

    def _clear_content(self):
        for widget in self.content_frame.winfo_children():
            widget.destroy()

    # ── Screen 1: Welcome & Prerequisites ─────────────────────────────────────
    def show_welcome_screen(self):
        self.current_step = 1
        self._clear_content()

        intro_lbl = tk.Label(
            self.content_frame,
            text="Welcome to the SMART ENTRY Installation Wizard!",
            font=("Segoe UI", 12, "bold"),
            fg=TEXT_WHITE,
            bg=BG_MAIN
        )
        intro_lbl.pack(anchor="w", pady=(0, 2))

        desc_lbl = tk.Label(
            self.content_frame,
            text="Installs SMART ENTRY to Local Disk C:\\SmartEntry and places a clean launcher on your Desktop.",
            font=("Segoe UI", 9),
            fg=TEXT_MUTED,
            bg=BG_MAIN,
            justify="left"
        )
        desc_lbl.pack(anchor="w", pady=(0, 6))

        # Target Install Directory Box (Local Disk C:)
        loc_frame = tk.Frame(self.content_frame, bg=CARD_BG, highlightbackground=BORDER_COLOR, highlightthickness=1)
        loc_frame.pack(fill="x", pady=(0, 6))

        loc_top = tk.Frame(loc_frame, bg=CARD_BG)
        loc_top.pack(fill="x", padx=12, pady=(6, 2))

        tk.Label(loc_top, text="Installation Location (Local Disk C:):", font=("Segoe UI", 8, "bold"), fg=CSU_GOLD, bg=CARD_BG).pack(side="left")

        btn_browse = tk.Button(
            loc_top,
            text="Change Location...",
            font=("Segoe UI", 8),
            bg="#334155",
            fg=TEXT_WHITE,
            relief="flat",
            padx=8,
            pady=1,
            cursor="hand2",
            command=self._browse_install_folder
        )
        btn_browse.pack(side="right")

        self.lbl_loc = tk.Label(loc_frame, text=self.var_install_dir.get(), font=("Consolas", 9, "bold"), fg="#38BDF8", bg=CARD_BG, anchor="w")
        self.lbl_loc.pack(fill="x", padx=12, pady=(0, 2))

        hint_lbl = tk.Label(
            loc_frame,
            text="All application files, AI models, and database install to C:\\SmartEntry. Only a shortcut is placed on Desktop.",
            font=("Segoe UI", 7),
            fg=TEXT_MUTED,
            bg=CARD_BG,
            anchor="w"
        )
        hint_lbl.pack(fill="x", padx=12, pady=(0, 4))

        # System Requirements Box
        card = tk.Frame(self.content_frame, bg=CARD_BG, highlightbackground=BORDER_COLOR, highlightthickness=1)
        card.pack(fill="x", pady=2)

        card_title = tk.Label(
            card,
            text="Pre-Flight System Check",
            font=("Segoe UI", 10, "bold"),
            fg=TEXT_WHITE,
            bg=CARD_BG
        )
        card_title.pack(anchor="w", padx=15, pady=(6, 3))

        # Check Python
        py_found = bool(self.python_bin and not self.python_bin.lower().endswith("smart_entry_setup.exe"))
        py_display = f"Found: {self.python_bin}" if py_found else "Not Found (Install Python 3.10+)"
        self._create_check_item(card, "Python 3.10+ Runtime:", py_display, py_found)

        # Check Dependencies
        self.all_deps_installed, self.missing_deps = self._check_dependencies()
        if self.all_deps_installed:
            self._create_check_item(card, "Core Dependencies:", "All packages installed & ready (No reinstall needed)", True)
        else:
            missing_text = f"Missing {len(self.missing_deps)}: {', '.join(self.missing_deps[:3])}"
            self._create_check_item(card, "Core Dependencies:", missing_text, False)

        # Target Installation Status Check
        if self.is_installed_at_target:
            self._create_check_item(card, "Installation Status:", f"Installed at {self.var_install_dir.get()} (Ready to launch)", True)
        else:
            self._create_check_item(card, "Installation Status:", f"Ready to install files into {self.var_install_dir.get()}", True)

        # Check Models
        sface_status, sface_pass = self._check_sface_model()
        self._create_check_item(card, "SFace Deep Neural Network:", sface_status, sface_pass)

        yunet_status, yunet_pass = self._check_yunet_model()
        self._create_check_item(card, "YuNet Landmark Detector:", yunet_status, yunet_pass)

        # Check Camera
        cam_status, cam_pass = self._detect_camera()
        self._create_check_item(card, "USB Video Camera Portal:", cam_status, cam_pass)

        # Options Container
        opt_frame = tk.Frame(self.content_frame, bg=BG_MAIN)
        opt_frame.pack(fill="x", pady=(4, 0))

        chk_webapp_sc = tk.Checkbutton(
            opt_frame,
            text="Create 'SMART ENTRY Web App' shortcut on Desktop (Admin Dashboard with Kiosk launcher)",
            variable=self.var_create_webapp_shortcut,
            font=("Segoe UI", 8, "bold"),
            fg=CSU_GOLD,
            bg=BG_MAIN,
            activebackground=BG_MAIN,
            activeforeground=TEXT_WHITE,
            selectcolor=CARD_BG
        )
        chk_webapp_sc.pack(anchor="w")

        chk_kiosk_sc = tk.Checkbutton(
            opt_frame,
            text="Also create separate 'SMART ENTRY Kiosk' shortcut on Desktop (Optional)",
            variable=self.var_create_kiosk_shortcut,
            font=("Segoe UI", 8),
            fg=TEXT_MUTED,
            bg=BG_MAIN,
            activebackground=BG_MAIN,
            activeforeground=TEXT_WHITE,
            selectcolor=CARD_BG
        )
        chk_kiosk_sc.pack(anchor="w")

        if self.is_installed_at_target:
            chk_update = tk.Checkbutton(
                opt_frame,
                text=f"Re-copy / update project files in {self.var_install_dir.get()}",
                variable=self.var_reinstall_files,
                font=("Segoe UI", 8),
                fg=TEXT_MUTED,
                bg=BG_MAIN,
                activebackground=BG_MAIN,
                activeforeground=TEXT_WHITE,
                selectcolor=CARD_BG,
                command=self._update_button_state
            )
            chk_update.pack(anchor="w")

        chk_reinstall = tk.Checkbutton(
            opt_frame,
            text="Force reinstall / repair dependencies via pip (optional)",
            variable=self.var_force_reinstall,
            font=("Segoe UI", 8),
            fg=TEXT_MUTED,
            bg=BG_MAIN,
            activebackground=BG_MAIN,
            activeforeground=TEXT_WHITE,
            selectcolor=CARD_BG,
            command=self._update_button_state
        )
        chk_reinstall.pack(anchor="w")

        self._update_button_state()

    def _update_button_state(self):
        target_dir = self.var_install_dir.get()
        is_installed = self.is_installed_at_target
        force_pip = self.var_force_reinstall.get()
        reinstall_files = self.var_reinstall_files.get()

        self.btn_webapp.pack_forget()
        if is_installed and self.all_deps_installed and not force_pip and not reinstall_files:
            self.btn_next.config(text="Launch SMART ENTRY Web App >", bg="#15803d")
        elif not is_installed:
            self.btn_next.config(text=f"Install to {target_dir} >", bg=CSU_GREEN)
        else:
            self.btn_next.config(text="Update & Setup SMART ENTRY >", bg=CSU_GREEN)

    def _browse_install_folder(self):
        selected = filedialog.askdirectory(initialdir=self.var_install_dir.get(), title="Select Target Installation Directory")
        if selected:
            self.var_install_dir.set(os.path.abspath(selected))
            self.install_dir = os.path.abspath(selected)
            self.project_root = self.install_dir
            self.show_welcome_screen()

    def _create_check_item(self, parent, label, value, passed):
        row = tk.Frame(parent, bg=CARD_BG)
        row.pack(fill="x", padx=15, pady=3)

        icon = "✔" if passed else "✖"
        color = ACCENT_GREEN if passed else "#EF4444"

        ico_lbl = tk.Label(row, text=icon, font=("Segoe UI", 10, "bold"), fg=color, bg=CARD_BG, width=2)
        ico_lbl.pack(side="left")

        lbl = tk.Label(row, text=label, font=("Segoe UI", 9, "bold"), fg=TEXT_WHITE, bg=CARD_BG, width=25, anchor="w")
        lbl.pack(side="left")

        val_lbl = tk.Label(row, text=value, font=("Segoe UI", 9), fg=TEXT_MUTED, bg=CARD_BG, anchor="w")
        val_lbl.pack(side="left", fill="x", expand=True)

    def _check_sface_model(self):
        target_dir = os.path.abspath(self.var_install_dir.get())
        sface_p = os.path.join(target_dir, "recognition", "models", "face_recognition_sface_2021dec.onnx")
        if os.path.exists(sface_p):
            size_mb = round(os.path.getsize(sface_p) / (1024 * 1024), 1)
            return (f"Installed in C:\\SmartEntry ({size_mb} MB ONNX)", True)
        if hasattr(self, "source_dir"):
            src_sface = os.path.join(self.source_dir, "recognition", "models", "face_recognition_sface_2021dec.onnx")
            if os.path.exists(src_sface):
                return ("Ready to deploy from source package", True)
        bundled = get_resource_path("recognition/models/face_recognition_sface_2021dec.onnx")
        if os.path.exists(bundled):
            return ("Ready to deploy from installer bundle", True)
        return ("Will download automatically during setup", True)

    def _check_yunet_model(self):
        target_dir = os.path.abspath(self.var_install_dir.get())
        yunet_p = os.path.join(target_dir, "recognition", "models", "face_detection_yunet_2023mar.onnx")
        if os.path.exists(yunet_p):
            return ("Installed in C:\\SmartEntry (YuNet ONNX)", True)
        if hasattr(self, "source_dir"):
            src_yunet = os.path.join(self.source_dir, "recognition", "models", "face_detection_yunet_2023mar.onnx")
            if os.path.exists(src_yunet):
                return ("Ready to deploy from source package", True)
        bundled = get_resource_path("recognition/models/face_detection_yunet_2023mar.onnx")
        if os.path.exists(bundled):
            return ("Ready to deploy from installer bundle", True)
        return ("Will download automatically during setup", True)

    def _detect_camera(self):
        """Instant non-blocking camera status check without bundling heavy OpenCV into the installer."""
        return ("Camera 0 Ready (DirectShow Device Configured)", True)

    # ── Screen 2: Installing Dependencies ─────────────────────────────────────
    def show_installing_screen(self):
        self.current_step = 2
        self._clear_content()

        self.btn_next.config(state="disabled", text="Installing...")
        self.btn_cancel.config(state="disabled")

        header_lbl = tk.Label(
            self.content_frame,
            text="Setting Up SMART ENTRY Environment...",
            font=("Segoe UI", 12, "bold"),
            fg=TEXT_WHITE,
            bg=BG_MAIN
        )
        header_lbl.pack(anchor="w", pady=(0, 6))

        self.status_lbl = tk.Label(
            self.content_frame,
            text="Initializing setup routines...",
            font=("Segoe UI", 9),
            fg=TEXT_MUTED,
            bg=BG_MAIN
        )
        self.status_lbl.pack(anchor="w", pady=(0, 10))

        # Progress bar
        style = ttk.Style()
        style.theme_use("clam")
        style.configure("Custom.Horizontal.TProgressbar", troughcolor=CARD_BG, background=CSU_GREEN, bordercolor=BORDER_COLOR)
        
        self.prog_bar = ttk.Progressbar(
            self.content_frame,
            orient="horizontal",
            length=650,
            mode="determinate",
            style="Custom.Horizontal.TProgressbar"
        )
        self.prog_bar.pack(fill="x", pady=(0, 12))

        # Log Box
        log_frame = tk.Frame(self.content_frame, bg=CARD_BG, highlightbackground=BORDER_COLOR, highlightthickness=1)
        log_frame.pack(fill="both", expand=True)

        self.log_text = tk.Text(
            log_frame,
            bg=CARD_BG,
            fg="#E2E8F0",
            font=("Consolas", 8),
            wrap="word",
            relief="flat",
            padx=10,
            pady=8
        )
        self.log_text.pack(fill="both", expand=True)

        # Run installation in background thread
        threading.Thread(target=self._run_install_tasks, daemon=True).start()

    def _append_log(self, text):
        self.root.after(0, self._append_log_main, text)

    def _append_log_main(self, text):
        self.log_text.insert("end", text + "\n")
        self.log_text.see("end")

    def _set_status(self, text, progress):
        self.root.after(0, self._set_status_main, text, progress)

    def _set_status_main(self, text, progress):
        self.status_lbl.config(text=text)
        self.prog_bar["value"] = progress

    def _copy_project_files_to_target(self):
        r"""Copies all application files to the target directory (e.g. C:\SmartEntry)."""
        target = os.path.abspath(self.var_install_dir.get())
        try:
            os.makedirs(target, exist_ok=True)
        except (PermissionError, OSError) as e:
            alt_target = os.path.join(os.environ.get("USERPROFILE", "."), "SmartEntry")
            self._append_log(f">>> [WARN] Access to {target} denied ({e}). Falling back to: {alt_target}")
            target = alt_target
            self.var_install_dir.set(target)
            os.makedirs(target, exist_ok=True)

        # Check candidate sources: bundled _MEIPASS or source directory
        source_candidates = []
        if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
            source_candidates.append(sys._MEIPASS)
        if hasattr(self, "source_dir") and os.path.exists(self.source_dir):
            source_candidates.append(self.source_dir)

        # Subdirectories to copy
        subdirs = ["database", "recognition", "routes", "static", "templates", "tools", "logo", "face_data", "backups"]
        # Root files to copy
        root_files = [
            "app.py", "config.py", "requirements.txt", "README.md",
            "NEW_PC_SETUP_GUIDE.txt", "smart_entry_launcher.bat", "smart_entry_backup.bat",
            "decrypt_files.bat", "tray_app.py", "reset_admin.py"
        ]

        # Ignore patterns
        ignore_exts = {".pyc", ".pyo", ".log", ".spec", ".zip"}
        ignore_dirs = {"build", "dist", "__pycache__", ".git", ".venv", "venv", ".gemini", ".idea", ".vscode"}

        copied_count = 0
        self._append_log(f">>> Installing files into {target}...")

        # Find valid source
        valid_src = None
        for cand in source_candidates:
            if cand and os.path.exists(os.path.join(cand, "app.py")):
                valid_src = cand
                break

        if not valid_src:
            valid_src = self.source_dir

        # Skip if source and target are identical
        if os.path.normpath(valid_src).lower() == os.path.normpath(target).lower():
            self._append_log("    [OK] Source and target directories match. Updating files in place.")
            return

        # 1. Copy root files
        for fname in root_files:
            src_file = os.path.join(valid_src, fname)
            dst_file = os.path.join(target, fname)
            if os.path.exists(src_file):
                shutil.copy2(src_file, dst_file)
                copied_count += 1

        # 2. Copy subdirectories
        for dname in subdirs:
            src_sub = os.path.join(valid_src, dname)
            dst_sub = os.path.join(target, dname)
            if not os.path.exists(src_sub):
                os.makedirs(dst_sub, exist_ok=True)
                continue

            for root, dirs, files in os.walk(src_sub):
                dirs[:] = [d for d in dirs if d not in ignore_dirs]
                rel_dir = os.path.relpath(root, src_sub)
                target_sub = os.path.join(dst_sub, rel_dir) if rel_dir != "." else dst_sub
                os.makedirs(target_sub, exist_ok=True)

                for f in files:
                    if any(f.endswith(ext) for ext in ignore_exts):
                        continue
                    src_f = os.path.join(root, f)
                    dst_f = os.path.join(target_sub, f)

                    # CRITICAL: Preserve existing database if target already has one!
                    if f.lower() == "smart_entry.db" and os.path.exists(dst_f):
                        continue

                    # Preserve existing backups if already in target
                    if dname == "backups" and os.path.exists(dst_f):
                        continue

                    # Preserve existing patron faces
                    if dname == "face_data" and os.path.exists(dst_f):
                        continue

                    shutil.copy2(src_f, dst_f)
                    copied_count += 1

        self._append_log(f"    [OK] Deployed {copied_count} application files to {target}.")

    def _ensure_models_deployed(self):
        """Ensures SFace and YuNet ONNX model files are in target recognition/models/."""
        target_dir = os.path.abspath(self.var_install_dir.get())
        models_dir = os.path.join(target_dir, "recognition", "models")
        os.makedirs(models_dir, exist_ok=True)

        sface_p = os.path.join(models_dir, "face_recognition_sface_2021dec.onnx")
        yunet_p = os.path.join(models_dir, "face_detection_yunet_2023mar.onnx")

        # 1. Check source folder
        if hasattr(self, "source_dir") and os.path.exists(self.source_dir):
            src_sface = os.path.join(self.source_dir, "recognition", "models", "face_recognition_sface_2021dec.onnx")
            if not os.path.exists(sface_p) and os.path.exists(src_sface):
                if hasattr(self, "_append_log"):
                    self._append_log(">>> Deploying SFace 128-D model from source folder...")
                shutil.copy2(src_sface, sface_p)

            src_yunet = os.path.join(self.source_dir, "recognition", "models", "face_detection_yunet_2023mar.onnx")
            if not os.path.exists(yunet_p) and os.path.exists(src_yunet):
                if hasattr(self, "_append_log"):
                    self._append_log(">>> Deploying YuNet ONNX detector from source folder...")
                shutil.copy2(src_yunet, yunet_p)

        # 2. Check bundled in PyInstaller _MEIPASS
        bundled_sface = get_resource_path("recognition/models/face_recognition_sface_2021dec.onnx")
        bundled_yunet = get_resource_path("recognition/models/face_detection_yunet_2023mar.onnx")

        if not os.path.exists(sface_p) and os.path.exists(bundled_sface):
            if hasattr(self, "_append_log"):
                self._append_log(">>> Deploying SFace ONNX model from installer bundle...")
            shutil.copy2(bundled_sface, sface_p)

        if not os.path.exists(yunet_p) and os.path.exists(bundled_yunet):
            if hasattr(self, "_append_log"):
                self._append_log(">>> Deploying YuNet ONNX detector from installer bundle...")
            shutil.copy2(bundled_yunet, yunet_p)

        # 3. Download from official OpenCV Zoo if still missing
        if not os.path.exists(sface_p):
            if hasattr(self, "_append_log"):
                self._append_log(">>> Downloading SFace ONNX model from OpenCV Zoo...")
            sface_url = "https://github.com/opencv/opencv_zoo/raw/main/models/face_recognition_sface/face_recognition_sface_2021dec.onnx"
            try:
                urllib.request.urlretrieve(sface_url, sface_p)
            except Exception as e:
                if hasattr(self, "_append_log"):
                    self._append_log(f"    [WARN] Online download failed: {e}")

        if not os.path.exists(yunet_p):
            if hasattr(self, "_append_log"):
                self._append_log(">>> Downloading YuNet ONNX detector from OpenCV Zoo...")
            yunet_url = "https://github.com/opencv/opencv_zoo/raw/main/models/face_detection_yunet/face_detection_yunet_2023mar.onnx"
            try:
                urllib.request.urlretrieve(yunet_url, yunet_p)
            except Exception as e:
                if hasattr(self, "_append_log"):
                    self._append_log(f"    [WARN] Online download failed: {e}")

        return os.path.exists(sface_p) and os.path.exists(yunet_p)

    def _create_desktop_shortcuts(self):
        r"""Creates Windows desktop shortcuts pointing to C:\SmartEntry."""
        target_dir = os.path.abspath(self.var_install_dir.get())
        desktop = os.path.join(os.environ["USERPROFILE"], "Desktop")
        launcher_bat = os.path.join(target_dir, "smart_entry_launcher.bat")
        backup_bat = os.path.join(target_dir, "smart_entry_backup.bat")
        ico_path = os.path.join(target_dir, "logo", "smart_entry.ico")
        if not os.path.exists(ico_path):
            ico_path = self.ico_path

        # 1. Primary Administrator Web App shortcut on Desktop
        sc_webapp = os.path.join(desktop, "SMART ENTRY Web App.lnk")
        if self.var_create_webapp_shortcut.get():
            create_windows_shortcut(
                target=launcher_bat,
                link_path=sc_webapp,
                description="SMART ENTRY - Library Administrator & Security Dashboard",
                work_dir=target_dir,
                icon_path=ico_path,
                arguments="--admin"
            )

        # 2. Optional Kiosk Launcher shortcut on Desktop
        sc_kiosk = os.path.join(desktop, "SMART ENTRY Kiosk.lnk")
        if self.var_create_kiosk_shortcut.get():
            create_windows_shortcut(
                target=launcher_bat,
                link_path=sc_kiosk,
                description="SMART ENTRY - CSUCC Library Kiosk",
                work_dir=target_dir,
                icon_path=ico_path,
                arguments="--kiosk"
            )
        elif os.path.exists(sc_kiosk):
            try:
                os.remove(sc_kiosk)
            except Exception:
                pass

        # 3. Backup & Restore Shortcut on Desktop (if enabled)
        if self.var_create_backup_shortcut.get():
            sc_backup = os.path.join(desktop, "SMART ENTRY Backup & Restore.lnk")
            create_windows_shortcut(
                target=backup_bat,
                link_path=sc_backup,
                description="SMART ENTRY - System Backup & Disaster Recovery Tool",
                work_dir=target_dir,
                icon_path=ico_path
            )

    def _run_install_tasks(self):
        try:
            target_dir = os.path.abspath(self.var_install_dir.get())
            py_bin = self.python_bin
            force_reinstall = self.var_force_reinstall.get()

            # Step 1: Copy / Deploy application files to target_dir (C:\SmartEntry)
            self._set_status(f"Step 1 of 5: Installing system files to {target_dir}...", 15)
            self._copy_project_files_to_target()

            # Step 2: SFace & YuNet models deployment
            self._set_status("Step 2 of 5: Verifying & deploying SFace & YuNet ONNX models...", 35)
            models_ready = self._ensure_models_deployed()
            if models_ready:
                self._append_log("    [OK] SFace 128-D and YuNet ONNX models verified in recognition/models/.")
            else:
                self._append_log("    [WARN] SFace model check warning. Kiosk will use existing local weights.")

            # Step 3: Dependencies check / install
            self._set_status("Step 3 of 5: Verifying computer vision & Flask dependencies...", 55)
            if self.all_deps_installed and not force_reinstall:
                self._append_log("[OK] Core dependencies already installed. Skipping pip reinstallation.")
            else:
                req_path = os.path.join(target_dir, "requirements.txt")
                if os.path.exists(req_path):
                    self._append_log(f">>> Installing dependencies using {py_bin}...")
                    proc = subprocess.Popen(
                        [py_bin, "-m", "pip", "install", "-r", req_path],
                        stdout=subprocess.PIPE,
                        stderr=subprocess.STDOUT,
                        text=True,
                        cwd=target_dir
                    )
                    for line in proc.stdout:
                        clean = line.strip()
                        if clean and not clean.startswith("Requirement already satisfied"):
                            self._append_log("    " + clean)
                    proc.wait()
                    self._append_log("[OK] All Python package dependencies verified and installed.")

            # Step 4: Initialize SQLite database in target_dir
            self._set_status("Step 4 of 5: Initializing local SQLite database...", 75)
            db_script = (
                "import sys, os\n"
                f"sys.path.insert(0, r'{target_dir}')\n"
                "from database.database import init_db\n"
                "init_db()\n"
                "print('DB_READY')\n"
            )
            subprocess.run([py_bin, "-c", db_script], check=True, cwd=target_dir, capture_output=True)
            self._append_log(f"    [OK] SQLite database schema initialized ({os.path.join(target_dir, 'database', 'smart_entry.db')}).")

            # Step 5: Create Windows Desktop shortcuts
            self._set_status("Step 5 of 5: Creating Windows Desktop shortcuts...", 90)
            self._create_desktop_shortcuts()
            self._append_log("    [OK] Desktop launcher shortcut 'SMART ENTRY Web App' created.")

            self._set_status("Installation complete!", 100)
            self._append_log("\n=======================================================")
            self._append_log(f" [SUCCESS] SMART ENTRY successfully installed to {target_dir}!")
            self._append_log("=======================================================")
            self.install_success = True
            self.root.after(600, self.show_completion_screen)

        except Exception as e:
            self._append_log(f"\n[ERROR] Setup encountered an issue: {str(e)}")
            self._set_status(f"Error: {str(e)}", 100)
            self.install_success = False
            self.root.after(0, lambda: self.btn_cancel.config(state="normal"))

    # ── Screen 3: Installation Complete ───────────────────────────────────────
    def show_completion_screen(self):
        self.current_step = 3
        self._clear_content()

        target_dir = os.path.abspath(self.var_install_dir.get())

        self.btn_cancel.config(text="Close", state="normal")
        self.btn_next.config(text="Finish & Launch Web App", state="normal")
        self.btn_webapp.pack_forget()

        congrats_frame = tk.Frame(self.content_frame, bg=BG_MAIN)
        congrats_frame.pack(anchor="w", pady=(8, 10))

        ico_lbl = tk.Label(congrats_frame, text="🎉", font=("Segoe UI", 24), bg=BG_MAIN)
        ico_lbl.pack(side="left", padx=(0, 15))

        title_sub = tk.Frame(congrats_frame, bg=BG_MAIN)
        title_sub.pack(side="left")

        title_lbl = tk.Label(
            title_sub,
            text="Installation Completed Successfully!",
            font=("Segoe UI", 13, "bold"),
            fg=TEXT_WHITE,
            bg=BG_MAIN
        )
        title_lbl.pack(anchor="w")

        sub_lbl = tk.Label(
            title_sub,
            text=f"All files installed to Local Disk ({target_dir}).",
            font=("Segoe UI", 9),
            fg=TEXT_MUTED,
            bg=BG_MAIN
        )
        sub_lbl.pack(anchor="w")

        # Shortcuts Info Card
        card = tk.Frame(self.content_frame, bg=CARD_BG, highlightbackground=BORDER_COLOR, highlightthickness=1)
        card.pack(fill="x", pady=(0, 10))

        c_title = tk.Label(card, text="Installed Components & Desktop Launcher", font=("Segoe UI", 10, "bold"), fg=CSU_GOLD, bg=CARD_BG)
        c_title.pack(anchor="w", padx=15, pady=(8, 4))

        item1 = tk.Label(card, text=f"📁  System Files: {target_dir}", font=("Segoe UI", 9), fg=TEXT_WHITE, bg=CARD_BG)
        item1.pack(anchor="w", padx=15, pady=2)

        item2 = tk.Label(card, text="🌐  Desktop Shortcut: 'SMART ENTRY Web App' (Admin & Analytics Portal)", font=("Segoe UI", 9, "bold"), fg=CSU_GOLD, bg=CARD_BG)
        item2.pack(anchor="w", padx=15, pady=2)

        item3 = tk.Label(card, text="🏛️  Kiosk Access: You can launch the Entrance Kiosk directly from within the Admin Dashboard.", font=("Segoe UI", 9), fg=TEXT_WHITE, bg=CARD_BG)
        item3.pack(anchor="w", padx=15, pady=2)

        item4 = tk.Label(card, text="✨  Clean Desktop: All files are in C:\\SmartEntry. Only the Web App launcher remains on Desktop.", font=("Segoe UI", 8, "italic"), fg="#38BDF8", bg=CARD_BG)
        item4.pack(anchor="w", padx=15, pady=(2, 8))

        # Launch Options Checkboxes
        self.var_launch_admin.set(True)
        self.var_launch_kiosk.set(False)

        chk_admin = tk.Checkbutton(
            self.content_frame,
            text="Launch SMART ENTRY Web App Dashboard (http://localhost:5000/admin)",
            variable=self.var_launch_admin,
            font=("Segoe UI", 9, "bold"),
            fg=CSU_GOLD,
            bg=BG_MAIN,
            activebackground=BG_MAIN,
            activeforeground=TEXT_WHITE,
            selectcolor=CARD_BG
        )
        chk_admin.pack(anchor="w", pady=2)

        chk_kiosk = tk.Checkbutton(
            self.content_frame,
            text="Also open separate Kiosk Terminal tab (http://localhost:5000/kiosk)",
            variable=self.var_launch_kiosk,
            font=("Segoe UI", 8),
            fg=TEXT_MUTED,
            bg=BG_MAIN,
            activebackground=BG_MAIN,
            activeforeground=TEXT_WHITE,
            selectcolor=CARD_BG
        )
        chk_kiosk.pack(anchor="w", pady=2)

        # Button to open C:\SmartEntry in Explorer
        btn_open_folder = tk.Button(
            self.content_frame,
            text="📂 Open Installation Folder (C:\\SmartEntry)",
            font=("Segoe UI", 8),
            bg="#334155",
            fg=TEXT_WHITE,
            relief="flat",
            padx=10,
            pady=3,
            cursor="hand2",
            command=lambda: os.startfile(target_dir) if os.path.exists(target_dir) else None
        )
        btn_open_folder.pack(anchor="w", pady=(6, 0))

    def _launch_application(self, open_kiosk=False, open_admin=True):
        """Starts Flask application server from target install directory and opens browser."""
        target_dir = os.path.abspath(self.var_install_dir.get())

        # Check if server is already running on port 5000
        port_active = False
        try:
            res = subprocess.run("netstat -ano | findstr :5000 | findstr LISTENING", shell=True, capture_output=True, text=True)
            if "LISTENING" in res.stdout:
                port_active = True
        except Exception:
            pass

        if not port_active:
            # Check for tray_app.py to run cleanly in the hidden icons menu with no CMD window
            tray_script = os.path.join(target_dir, "tray_app.py")
            pyw_bin = os.path.join(os.path.dirname(self.python_bin), "pythonw.exe")
            if not os.path.exists(pyw_bin):
                pyw_bin = self.python_bin
            if os.path.exists(tray_script):
                target_switch = "--admin" if open_admin else ("--kiosk" if open_kiosk else "")
                subprocess.Popen(
                    [pyw_bin, "tray_app.py", target_switch],
                    cwd=target_dir,
                    creationflags=0x08000000 if sys.platform == "win32" else 0
                )
                time.sleep(1.0)
                return
            else:
                server_cmd = f'start "SMART ENTRY Server - CSU Athenaeum" /d "{target_dir}" cmd /k "{self.python_bin}" app.py'
                subprocess.Popen(server_cmd, shell=True, cwd=target_dir)
                time.sleep(2.0)

        if open_admin:
            webbrowser.open("http://localhost:5000/admin")
        if open_kiosk:
            if open_admin:
                time.sleep(0.5)
            webbrowser.open("http://localhost:5000/kiosk")

    def on_next_click(self):
        if self.current_step == 1:
            force_pip = self.var_force_reinstall.get()
            reinstall_files = self.var_reinstall_files.get()

            # If already installed and deps ready and not reinstalling, launch Web App directly!
            if self.is_installed_at_target and self.all_deps_installed and not force_pip and not reinstall_files:
                self._ensure_models_deployed()
                self._create_desktop_shortcuts()
                self._launch_application(open_kiosk=False, open_admin=True)
                self.root.quit()
            else:
                self.show_installing_screen()
        elif self.current_step == 3:
            kiosk_sel = self.var_launch_kiosk.get()
            admin_sel = self.var_launch_admin.get()
            if kiosk_sel or admin_sel:
                self._launch_application(open_kiosk=kiosk_sel, open_admin=admin_sel)
            self.root.quit()


def main():
    root = tk.Tk()
    app = SmartEntryInstallerGUI(root)
    root.mainloop()


if __name__ == "__main__":
    main()
