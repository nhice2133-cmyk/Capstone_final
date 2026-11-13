from playwright.sync_api import sync_playwright

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    page = browser.new_page()
    page.goto("http://localhost:5000/kiosk")
    page.wait_for_load_state("networkidle")
    print("Kiosk loaded successfully.")

    # 1. Verify studentIdDisplay is NOT in DOM
    student_id_el = page.query_selector("#studentIdDisplay")
    print(f"studentIdDisplay in DOM: {bool(student_id_el)}")
    assert student_id_el is None, "#studentIdDisplay must not exist in the DOM!"

    # 2. Test Purpose Selection display
    mock_recognized = {
        "status": "recognized",
        "student_db_id": 42,
        "full_name": "Maria Clara Santos",
        "student_id": "2026-9999",
        "program": "Bachelor of Science in Computer Science",
        "face_box": {"x": 0.3, "y": 0.2, "w": 0.4, "h": 0.5}
    }
    page.evaluate("(data) => handleRecognitionResult(data)", mock_recognized)

    page_text = page.inner_text("#infoPanel")
    print("\n--- Info Panel Text (Purpose Selection) ---")
    print(page_text)
    print("------------------------------------------")

    assert "Maria Clara Santos" in page_text, "Full name must be displayed"
    assert "Computer Science" in page_text, "Program must be displayed"
    assert "2026-9999" not in page_text, "Student ID must NOT be displayed on public monitor!"

    # 3. Test Already Logged display
    mock_already_logged = {
        "status": "already_logged",
        "student_db_id": 42,
        "full_name": "Maria Clara Santos",
        "student_id": "2026-9999",
        "program": "Bachelor of Science in Computer Science",
        "time_in": "08:15:00",
        "face_box": {"x": 0.3, "y": 0.2, "w": 0.4, "h": 0.5}
    }
    page.evaluate("(data) => handleRecognitionResult(data)", mock_already_logged)

    page_text_already = page.inner_text("#infoPanel")
    print("\n--- Info Panel Text (Already Logged) ---")
    print(page_text_already)
    print("----------------------------------------")

    assert "Maria Clara Santos" in page_text_already, "Full name must be displayed"
    assert "Computer Science" in page_text_already, "Program must be displayed"
    assert "8:15 AM" in page_text_already, "Time In must be displayed"
    assert "2026-9999" not in page_text_already, "Student ID must NOT be displayed on public monitor!"

    browser.close()
    print("\n[SUCCESS] Data Privacy Act compliance verified: Zero Student IDs exposed on public screen!")

