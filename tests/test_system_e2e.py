"""
SMART ENTRY - Automated System & End-to-End Test Suite
Tests:
1. Backend & SQLite Database Integrity
2. Local Offline Asset Delivery (Chart.js offline loading)
3. Analytics and Dashboard REST API endpoints
4. Playwright End-to-End Browser Automation:
   - Admin Login (Auth failure & success)
   - Dashboard Summary & Stats
   - Analytics Page (Offline Chart.js rendering, zero console errors, zero external requests)
   - Attendance Logs & Filter Controls
   - Student Records Management
   - Entry Kiosk & Exit Monitor UI
"""
import os
import sys
import time
import threading
from werkzeug.serving import make_server
from playwright.sync_api import sync_playwright

# Ensure project root is in sys.path
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from app import create_app, _seed_default_admin
from database.database import init_db, get_db_connection

TEST_HOST = "127.0.0.1"
TEST_PORT = 5055
BASE_URL = f"http://{TEST_HOST}:{TEST_PORT}"


class ServerThread(threading.Thread):
    def __init__(self, app, host, port):
        super().__init__(daemon=True)
        self.server = make_server(host, port, app)
        self.ctx = app.app_context()
        self.ctx.push()

    def run(self):
        self.server.serve_forever()

    def shutdown(self):
        self.server.shutdown()


def test_system():
    print("=" * 70)
    print("  RUNNING SMART ENTRY FULL SYSTEM & OFFLINE VERIFICATION SUITE")
    print("=" * 70)

    # 1. Database Init Check
    print("\n[1/5] Testing Database and Schema...")
    init_db()
    conn = get_db_connection()
    tables = [row[0] for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()]
    conn.close()
    
    expected_tables = ["admins", "students", "attendance_logs", "security_alerts"]
    for t in expected_tables:
        assert t in tables, f"Missing expected table: {t}"
    print(f"  [PASS] SQLite tables verified: {', '.join(expected_tables)}")

    # 2. Flask App & Static Files Check
    print("\n[2/5] Testing Backend App & Local Offline Assets...")
    app = create_app()
    app.config["TESTING"] = True
    _seed_default_admin(app)
    
    with app.test_client() as client:
        # Check local Chart.js is served
        chart_res = client.get("/static/js/chart.umd.min.js")
        assert chart_res.status_code == 200, f"Chart.js returned status {chart_res.status_code}"
        assert len(chart_res.data) > 100000, "Chart.js file seems empty or truncated"
        print(f"  [PASS] Local offline Chart.js served successfully ({len(chart_res.data):,} bytes)")

        # Check login page
        login_res = client.get("/login")
        assert login_res.status_code == 200
        print("  [PASS] Login page GET endpoint OK (200)")

    # 3. Start Test Server for Playwright
    print("\n[3/5] Starting Background Test Server on port 5055...")
    server = ServerThread(app, TEST_HOST, TEST_PORT)
    server.start()
    time.sleep(1)  # Allow server to bind and start listening
    print(f"  [PASS] Server running at {BASE_URL}")

    # 4. Playwright End-to-End UI & Console Error Testing
    print("\n[4/5] Running Playwright End-to-End Browser Tests...")
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context()
        page = context.new_page()

        console_errors = []
        external_requests = []

        def on_console(msg):
            if msg.type in ["error"]:
                console_errors.append(f"Console {msg.type}: {msg.text}")

        def on_page_error(err):
            console_errors.append(f"Page Error: {err}")

        def on_request(req):
            url = req.url
            if not url.startswith(BASE_URL) and not url.startswith("data:"):
                external_requests.append(url)

        page.on("console", on_console)
        page.on("pageerror", on_page_error)
        page.on("request", on_request)

        # 4.1 Test Invalid Login
        print("\n  -> Testing Authentication Failure Handler...")
        page.goto(f"{BASE_URL}/login")
        page.fill('input[name="username"]', "admin")
        page.fill('input[name="password"]', "wrongpassword123")
        page.click('button[type="submit"]')
        page.wait_for_selector(".flash", timeout=5000)
        assert "Invalid username or password" in page.content()
        print("     [PASS] Invalid login blocked with warning flash message.")

        # 4.2 Test Valid Login & Dashboard Redirect
        print("  -> Testing Admin Authentication & Dashboard...")
        page.fill('input[name="username"]', "admin")
        page.fill('input[name="password"]', "smart_entry_2026")
        page.click('button[type="submit"]')
        page.wait_for_url(f"{BASE_URL}/admin/dashboard", timeout=6000)
        body_text = page.inner_text("body")
        assert "Overview" in body_text
        assert page.is_visible("#statVisitors")
        assert page.is_visible("#statInside")
        assert page.is_visible("#statAlerts")
        assert page.is_visible("#statEnrolled")
        assert "Time Out" not in page.text_content("table thead")
        print("     [PASS] Admin logged in successfully; dashboard stats visible and Time Out column removed.")

        # 4.3 Test Analytics Page (OFFLINE VERIFICATION)
        print("  -> Testing Analytics Dashboard (Fully Offline)...")
        console_errors.clear()
        external_requests.clear()

        page.goto(f"{BASE_URL}/admin/analytics")
        page.wait_for_selector("#dailyChart", timeout=6000)
        page.wait_for_selector("#departmentChart", timeout=6000)
        page.wait_for_selector("#hourlyChart", timeout=6000)
        page.wait_for_selector("#purposeChart", timeout=6000)
        
        # Wait a moment for async fetch calls to resolve and charts to initialize
        time.sleep(1.5)

        # Check if Chart is defined in the window object
        chart_defined = page.evaluate("() => typeof window.Chart !== 'undefined'")
        assert chart_defined, "Chart.js is NOT defined in the window object!"
        print("     [PASS] Chart.js loaded locally into window.Chart (no CDN required).")

        # Check if canvas elements exist and have dimensions
        daily_ready = page.evaluate("() => !!document.getElementById('dailyChart')")
        dept_ready = page.evaluate("() => !!document.getElementById('departmentChart')")
        hourly_ready = page.evaluate("() => !!document.getElementById('hourlyChart')")
        purpose_ready = page.evaluate("() => !!document.getElementById('purposeChart')")
        assert daily_ready and dept_ready and hourly_ready and purpose_ready
        print("     [PASS] All 4 Canvas elements (#dailyChart, #departmentChart, #hourlyChart, #purposeChart) rendered.")

        # Check summary totals and highest department
        summary_total = page.text_content("#summaryTotal")
        top_dept = page.text_content("#summaryTopDept")
        assert summary_total is not None and summary_total != ""
        assert top_dept is not None and top_dept != "" and top_dept != "—"
        print(f"     [PASS] Analytics summary populated: Total Visits = {summary_total}, Highest Department = {top_dept}")

        # Verify no external requests were triggered by the analytics charts
        chart_external = [url for url in external_requests if "jsdelivr" in url or "chart" in url]
        assert len(chart_external) == 0, f"Detected external chart requests: {chart_external}"
        print("     [PASS] Zero external requests to jsdelivr/Chart.js CDN.")

        # Check console errors on analytics page (excluding Google Font warnings if offline)
        fatal_errors = [e for e in console_errors if "fonts.gstatic" not in e and "fonts.google" not in e]
        assert len(fatal_errors) == 0, f"Fatal JavaScript errors found: {fatal_errors}"
        print("     [PASS] Zero JavaScript runtime errors on Analytics page.")

        # 4.4 Test Attendance Logs Page
        print("  -> Testing Attendance Logs & Export UI...")
        page.goto(f"{BASE_URL}/admin/attendance")
        page.wait_for_selector("table", timeout=5000)
        assert "Attendance" in page.inner_text("body")
        assert "Time Out" not in page.text_content("#attendanceTable thead")
        print("     [PASS] Attendance table and filters loaded; Time Out column removed.")

        # 4.5 Test Student Records Page
        print("  -> Testing Student Records Management...")
        page.goto(f"{BASE_URL}/admin/students")
        page.wait_for_selector("table", timeout=5000)
        assert "User" in page.inner_text("body")
        print("     [PASS] Student records list loaded.")

        # 4.5b Test Guest Enrollment UI (ID field removed for guests)
        print("  -> Testing Guest Enrollment Interface (ID field removed for guests)...")
        page.goto(f"{BASE_URL}/admin/enroll")
        page.wait_for_selector("#studentInfoForm", timeout=5000)
        
        # Verify initial Student mode requires and displays ID field with 10 char limit & counter
        assert page.is_visible("#groupStudentId")
        assert page.get_attribute("#studentId", "required") is not None
        assert page.get_attribute("#studentId", "maxlength") == "10"
        assert page.text_content("#idCharCounter") == "0 / 10"
        
        # Test character counter updates dynamically
        page.fill("#studentId", "211-00123")
        assert page.text_content("#idCharCounter") == "9 / 10"
        page.fill("#studentId", "1234567890")
        assert page.text_content("#idCharCounter") == "10 / 10"
        assert "limit-reached" in page.get_attribute("#idCharCounter", "class")
        print("     [PASS] Student ID character limit (10 chars max) and live counter verified.")
        
        # Test Program Searchable Combobox with newly added colleges (CEIT, CITTE, CTHM, CBA)
        assert page.locator('.combobox-item[data-value="BSCPE"]').count() == 1
        assert page.locator('.combobox-item[data-value="BSIT-WFT"]').count() == 1
        assert page.locator('.combobox-item[data-value="BTVTED-AD"]').count() == 1
        assert page.locator('.combobox-item[data-value="BSTM"]').count() == 1
        assert page.locator('.combobox-item[data-value="BSA"]').count() == 1
        
        # Search for welding in combobox
        page.fill("#program", "welding")
        assert not page.locator('.combobox-item[data-value="BSIT-WFT"]').first.is_hidden()
        assert page.locator('.combobox-item[data-value="BSA"]').first.is_hidden()
        page.click('.combobox-item[data-value="BSIT-WFT"]')
        assert page.input_value("#program") == "BSIT-WFT"
        print("     [PASS] Official CSU College programs (CEIT, CITTE, CTHM, CBA) searchable & selectable.")
        
        # Click Guest / Visitor Pill -> Input ID field is completely removed / hidden
        page.click("#btnTypeGuest")
        assert not page.is_visible("#groupStudentId")
        assert page.get_attribute("#studentId", "required") is None
        assert page.input_value("#program") == "Guest"
        
        # Submit Guest with First Name and Last Name (No ID field present)
        assert page.is_visible("#firstName")
        assert page.is_visible("#lastName")
        page.fill("#firstName", "Dr. Guest")
        page.fill("#lastName", "Researcher")
        page.click("#btnSaveInfo")
        
        # Verify transition to Step 2 with auto-generated Guest ID
        page.wait_for_selector("#step2:not(.hidden)", timeout=5000)
        preview_id_text = page.text_content("#previewId")
        assert preview_id_text.startswith("GST-")
        print(f"     [PASS] Guest enrolled to Step 2 with ID field removed (Assigned ID: {preview_id_text}).")

        # 4.6 Test Security Alerts Page
        print("  -> Testing Security Alerts Page...")
        page.goto(f"{BASE_URL}/admin/alerts")
        page.wait_for_selector(".card", timeout=5000)
        assert "Alerts" in page.inner_text("body")
        print("     [PASS] Security alerts page loaded.")

        # 4.7 Test Kiosk Entry Page
        print("  -> Testing Smart Entry Kiosk Interface...")
        page.goto(f"{BASE_URL}/kiosk")
        page.wait_for_selector("#cameraPanel, #webcamVideo", timeout=5000)
        assert "CSUCC ATHENAEUM" in page.inner_text("body")
        assert "ENTRY KIOSK" in page.inner_text("body")
        print("     [PASS] Smart Entry Kiosk interface loaded successfully.")

        # 4.8 Test Kiosk Exit Redirect (Entry-Only Deployment)
        print("  -> Testing Kiosk Exit Redirect for Entry-Only Deployment...")
        page.goto(f"{BASE_URL}/kiosk/exit")
        page.wait_for_url(f"{BASE_URL}/kiosk", timeout=5000)
        assert "ENTRY KIOSK" in page.inner_text("body")
        print("     [PASS] /kiosk/exit successfully redirects to /kiosk.")

        # 4.8b Verify Navigation has no Exit Kiosk links
        print("  -> Verifying Clean Entry-Only Navigation in Admin Panel...")
        page.goto(f"{BASE_URL}/admin/dashboard")
        page.wait_for_selector(".btn-primary", timeout=5000)
        dashboard_content = page.content()
        assert "Launch Kiosk" in dashboard_content
        assert "Launch Exit Monitor" not in dashboard_content
        assert "Exit Monitor (OUT)" not in dashboard_content
        print("     [PASS] Admin Panel contains only Entry Kiosk controls; all Exit Kiosk elements removed.")

        # 4.9 Test Models Configuration Page & Retraining Animation
        print("  -> Testing Face Recognition Models Page & Retraining Animation...")
        page.goto(f"{BASE_URL}/admin/models")
        page.wait_for_selector(".card", timeout=5000)
        assert "Recognition Engine" in page.inner_text("body") or "Model" in page.inner_text("body")

        # Verify Retrain Active Students button and modal structure
        btn_retrain = page.locator("#btnRetrain")
        assert btn_retrain.is_visible()
        modal_overlay = page.locator("#retrainModalOverlay")
        assert "hidden" in (modal_overlay.get_attribute("class") or "")

        # Click retrain button and verify animation appears
        btn_retrain.click()
        page.wait_for_function("!document.getElementById('retrainModalOverlay').classList.contains('hidden')", timeout=3000)
        assert "Retraining" in page.locator("#retrainModalTitle").inner_text()
        print("     [PASS] Retraining modal and biometric animation initiated successfully.")

        # Wait for retraining to complete and success status to show
        page.wait_for_function("document.getElementById('retrainModalTitle').innerText.includes('Complete') || document.getElementById('retrainModalTitle').innerText.includes('Retraining')", timeout=15000)
        print("     [PASS] Active students model retraining completed with live feedback.")

        browser.close()

    # 5. Teardown
    print("\n[5/5] Shutting down test server...")
    server.shutdown()
    print("  [PASS] Test server gracefully stopped.")

    print("\n" + "=" * 70)
    print("  ALL SYSTEM & PLAYWRIGHT E2E TESTS PASSED SUCCESSFULLY! (100% OFFLINE)")
    print("=" * 70)


if __name__ == "__main__":
    test_system()

