"""
SMART ENTRY — System Tray Background Server Runner
CSUCC Athenaeum Library Kiosk System
---------------------------------------------------
Runs the Flask application silently in the background with an icon
in the Windows Notification Area (Hidden Icons Menu `^`).
Provides instant access to the Web App and Kiosk with no visible CMD window.
"""

import os
import sys
import time
import socket
import logging
import threading
import webbrowser
from datetime import timedelta
from pathlib import Path

# Ensure working directory is project root
PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
os.chdir(PROJECT_ROOT)
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

# Suppress standard werkzeug access logs to keep background execution quiet
log = logging.getLogger('werkzeug')
log.setLevel(logging.ERROR)

def is_port_in_use(port: int = 5000) -> bool:
    """Checks whether localhost:port is already listening."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(0.5)
        return s.connect_ex(("127.0.0.1", port)) == 0

def kill_process_on_port(port: int = 5000):
    """Terminates any process currently listening on the specified port."""
    if sys.platform == "win32":
        try:
            import subprocess
            out = subprocess.check_output("netstat -ano", shell=True, text=True, creationflags=0x08000000)
            pids = set()
            for line in out.splitlines():
                if f":{port}" in line and "LISTENING" in line:
                    parts = line.strip().split()
                    if parts:
                        pids.add(parts[-1])
            for pid in pids:
                subprocess.run(["taskkill", "/F", "/PID", pid], capture_output=True, creationflags=0x08000000)
        except Exception:
            pass

class SmartEntryTrayApp:
    def __init__(self, open_target: str = None):
        self.open_target = open_target
        self.server = None
        self.server_thread = None
        self.tray_icon = None
        self.is_running = True
        self.port = 5000
        self.ico_path = os.path.join(PROJECT_ROOT, "logo", "smart_entry.ico")

    def start_flask_server(self):
        """Initializes and runs the Flask WSGI server in a background thread."""
        try:
            from config import Config
            from database.database import init_db
            from app import create_app, _seed_default_admin
            from werkzeug.serving import make_server

            os.makedirs(Config.FACE_DATA_DIR, exist_ok=True)
            os.makedirs(Config.ALERTS_SNAPSHOT_DIR, exist_ok=True)
            os.makedirs(os.path.join("recognition", "haarcascade"), exist_ok=True)

            init_db()
            app = create_app()
            _seed_default_admin(app)

            self.server = make_server("0.0.0.0", self.port, app, threaded=True)
            self.server_thread = threading.Thread(target=self.server.serve_forever, daemon=True)
            self.server_thread.start()
            return True
        except Exception as e:
            # Fallback if port conflict or initialization error
            return False

    def open_admin(self, icon=None, item=None):
        webbrowser.open(f"http://localhost:{self.port}/admin")

    def open_kiosk(self, icon=None, item=None):
        webbrowser.open(f"http://localhost:{self.port}/kiosk")

    def show_status(self, icon=None, item=None):
        # Open the system health & diagnostics page
        webbrowser.open(f"http://localhost:{self.port}/admin")

    def stop_server_and_exit(self, icon=None, item=None):
        """Cleanly stops the server and removes the system tray icon."""
        self.is_running = False
        try:
            if self.server:
                threading.Thread(target=self.server.shutdown, daemon=True).start()
        except Exception:
            pass

        try:
            if self.tray_icon:
                self.tray_icon.stop()
        except Exception:
            pass

        # Clean termination
        time.sleep(0.3)
        os._exit(0)

    def run(self):
        # 1. Check if server is already active on port 5000
        server_already_up = is_port_in_use(self.port)

        if not server_already_up:
            started = self.start_flask_server()
            if not started:
                # Retry once after freeing port
                kill_process_on_port(self.port)
                time.sleep(0.5)
                self.start_flask_server()

        # 2. Wait up to 2 seconds for server to be responsive
        for _ in range(20):
            if is_port_in_use(self.port):
                break
            time.sleep(0.1)

        # 3. Handle immediate target switch
        if self.open_target == "admin":
            threading.Thread(target=lambda: (time.sleep(0.3), self.open_admin()), daemon=True).start()
        elif self.open_target == "kiosk":
            threading.Thread(target=lambda: (time.sleep(0.3), self.open_kiosk()), daemon=True).start()

        # If server was already up and another tray app is likely running, just opening browser and exiting
        if server_already_up:
            return

        # 4. Initialize System Tray Icon
        self._setup_tray_icon()

    def _setup_tray_icon(self):
        try:
            import pystray
            from PIL import Image

            if os.path.exists(self.ico_path):
                img = Image.open(self.ico_path)
            else:
                # Fallback blank emerald icon if ico is missing
                img = Image.new('RGB', (64, 64), color=(13, 92, 58))

            menu = pystray.Menu(
                pystray.MenuItem("🌐 Open SMART ENTRY Web App", self.open_admin, default=True),
                pystray.MenuItem("🏛️ Open Smart Entry Kiosk", self.open_kiosk),
                pystray.Menu.SEPARATOR,
                pystray.MenuItem("📊 Server: Running (Port 5000)", self.show_status),
                pystray.Menu.SEPARATOR,
                pystray.MenuItem("⏹️ Stop Server & Exit", self.stop_server_and_exit)
            )

            self.tray_icon = pystray.Icon(
                "SmartEntryKiosk",
                img,
                "SMART ENTRY Server (CSUCC Athenaeum)",
                menu
            )

            # Optional: Show a brief balloon notification that server is active in tray
            try:
                self.tray_icon.notify(
                    "CSUCC Athenaeum Kiosk Server is running in the background.",
                    "SMART ENTRY Server Active"
                )
            except Exception:
                pass

            # Run tray loop on main thread (required by Windows message loop)
            self.tray_icon.run()

        except Exception as e:
            # Silent background wait fallback if pystray is unavailable
            while self.is_running:
                time.sleep(1)


def main():
    target = None
    if len(sys.argv) > 1:
        arg = sys.argv[1].lower()
        if arg in ("--admin", "-a", "admin"):
            target = "admin"
        elif arg in ("--kiosk", "-k", "kiosk"):
            target = "kiosk"
        elif arg in ("--stop", "-s", "stop", "exit"):
            kill_process_on_port(5000)
            print("[OK] Stopped SMART ENTRY server on port 5000.")
            sys.exit(0)

    app = SmartEntryTrayApp(open_target=target)
    app.run()


if __name__ == "__main__":
    main()
