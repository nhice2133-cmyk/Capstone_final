import os
import sys
import tempfile
import subprocess

def create_windows_shortcut(target: str, link_path: str, description: str = "", work_dir: str = "", icon_path: str = ""):
    """
    Creates a Windows .lnk shortcut using native Windows Script Host (CScript/WScript).
    Works on all Windows versions with zero third-party dependencies.
    """
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

if __name__ == "__main__":
    desktop = os.path.join(os.environ["USERPROFILE"], "Desktop")
    test_link = os.path.join(desktop, "TEST_SHORTCUT.lnk")
    success = create_windows_shortcut(sys.executable, test_link, "Python Test")
    print("Shortcut created:", success)
    if os.path.exists(test_link):
        os.remove(test_link)
        print("Test shortcut cleaned up successfully.")

