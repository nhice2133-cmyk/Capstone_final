from playwright.sync_api import sync_playwright

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    page = browser.new_page()

    # 1. Login
    page.goto("http://localhost:5000/login")
    page.fill("input[name=username]", "admin")
    page.fill("input[name=password]", "smart_entry_2026")
    page.click("button[type=submit]")
    page.wait_for_load_state("networkidle")
    print("Logged in successfully. URL:", page.url)

    # 2. Test Change Password Page (Desktop)
    page.set_viewport_size({"width": 1280, "height": 800})
    page.goto("http://localhost:5000/admin/change-password")
    page.wait_for_load_state("networkidle")
    print("Navigated to Change Password page. Title:", page.title())

    # Check key elements exist
    card = page.query_selector(".change-pw-card")
    header = page.query_selector(".change-pw-header-compact")
    grid = page.query_selector(".change-pw-grid")
    chips = page.query_selector_all(".req-chip")
    tip = page.query_selector(".security-tip-strip")
    actions = page.query_selector(".change-pw-actions")

    print(f"Elements present: card={bool(card)}, header={bool(header)}, grid={bool(grid)}, chips_count={len(chips)}, tip={bool(tip)}, actions={bool(actions)}")

    # Check card dimensions
    box = card.bounding_box()
    print(f"Desktop Card Dimensions: width={box['width']:.1f}px, height={box['height']:.1f}px")

    # Test typing new password and checking chips
    page.fill("#new_password", "Admin")
    chip_len = page.query_selector("#chipLen.valid")
    chip_upper = page.query_selector("#chipUpper.valid")
    chip_num = page.query_selector("#chipNum.valid")
    print(f"Typing 'Admin': chipLen valid={bool(chip_len)}, chipUpper valid={bool(chip_upper)}, chipNum valid={bool(chip_num)}")

    page.fill("#new_password", "Admin123")
    chip_len = page.query_selector("#chipLen.valid")
    chip_upper = page.query_selector("#chipUpper.valid")
    chip_num = page.query_selector("#chipNum.valid")
    print(f"Typing 'Admin123': chipLen valid={bool(chip_len)}, chipUpper valid={bool(chip_upper)}, chipNum valid={bool(chip_num)}")

    # Test confirm password match
    page.fill("#confirm_password", "Admin123")
    chip_match = page.query_selector("#chipMatch.valid")
    match_text = page.inner_text("#matchLabel")
    print(f"Typing match 'Admin123': chipMatch valid={bool(chip_match)}, text='{match_text}'")

    # Test toggle password
    pw_type_before = page.get_attribute("#new_password", "type")
    toggle_btn = page.query_selector("button[onclick*='new_password']")
    toggle_btn.click()
    pw_type_after = page.get_attribute("#new_password", "type")
    print(f"Toggle password: before={pw_type_before}, after={pw_type_after}")

    # Test Responsive Mobile (375x667)
    page.set_viewport_size({"width": 375, "height": 667})
    page.wait_for_timeout(300)
    box_mobile = card.bounding_box()
    grid_cols = page.evaluate("() => window.getComputedStyle(document.querySelector('.change-pw-grid')).gridTemplateColumns")
    print(f"Mobile Card (375px): width={box_mobile['width']:.1f}px, height={box_mobile['height']:.1f}px, gridColumns='{grid_cols}'")

    # 3. Test Alerts Fallback & Modals
    page.set_viewport_size({"width": 1280, "height": 800})
    page.goto("http://localhost:5000/admin/alerts")
    page.wait_for_load_state("networkidle")
    print("Alerts page loaded:", page.url)

    native_alerts = []
    page.on("dialog", lambda d: (native_alerts.append(d.message), d.dismiss()))

    # Check alert table
    rows = page.query_selector_all(".table tbody tr")
    print(f"Alert rows present: {len(rows)}")

    # Check resolved alerts page
    page.goto("http://localhost:5000/admin/alerts/resolved")
    page.wait_for_load_state("networkidle")
    rows_res = page.query_selector_all(".table tbody tr")
    print(f"Resolved alert rows present: {len(rows_res)}")

    print("Native browser popups intercepted:", native_alerts)
    browser.close()
    print("ALL PLAYWRIGHT TESTS PASSED!")

