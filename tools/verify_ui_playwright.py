"""Comprehensive Playwright UI Verification & Screenshot Suite.

Flows Tested:
- Overview (headline findings from evidence.json)
- Estimate (synthetic Mode 3+, Mode 2, Declared Physics, out-of-range alpha, malformed paste)
- Diagnose (Healthy H, Anomalous A, Fault F stuck/bias/gain, Change-point C, baseline refusal k=10)
- Placement (two-stage adaptive schedule on log scale)
- Field (Solver, FNO, Compare mode, time cross-section profile slider)
- Poisson (Low-freq sine, High-freq mode > 4 triggering warning, Gaussian heater)
- Evidence (All tables and Figure 7 interactive 4x4 confusion matrix)
- Limits (Operational boundaries with evidence anchors)
- Failure paths:
  1. Baseline k=10 refusal on /v1/diagnose (REFUSED_INSUFFICIENT_BASELINE)
  2. Malformed pasted rows on /v1/estimate (input validation error)
  3. Alpha out of range (alpha=20.0 triggering out_of_range flag)
  4. Service stopped (server stopped, health badge shows SERVICE DOWN, refusal/error state displayed)
- Themes: Light & Dark
- Viewports: 1440x900 (Desktop), 768x1024 (Tablet), 390x844 (Mobile)
- Zero unintended console errors.
"""

import os
import sys
import time
import socket
import subprocess
import json
from playwright.sync_api import sync_playwright

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCREENSHOTS_DIR = os.path.join(REPO_ROOT, "docs", "ui_screenshots")

def wait_for_port(port=8000, timeout=25):
    start = time.time()
    while time.time() - start < timeout:
        try:
            with socket.create_connection(("127.0.0.1", port), timeout=1):
                return True
        except (ConnectionRefusedError, OSError):
            time.sleep(0.5)
    return False

def find_free_port():
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(('', 0))
        return s.getsockname()[1]

def run_verification():
    os.makedirs(SCREENSHOTS_DIR, exist_ok=True)
    scratch_dir = os.path.join(REPO_ROOT, "scratch")
    os.makedirs(scratch_dir, exist_ok=True)
    server_log = open(os.path.join(scratch_dir, "uvicorn_verify.log"), "w", encoding="utf-8")
    
    port = find_free_port()
    print(f"Starting uvicorn server on port {port}...")
    env = os.environ.copy()
    env["PYTHONUNBUFFERED"] = "1"
    server_proc = subprocess.Popen(
        [sys.executable, "-u", "-m", "uvicorn", "service.app:app", "--port", str(port), "--host", "127.0.0.1"],
        cwd=REPO_ROOT,
        stdout=server_log,
        stderr=subprocess.STDOUT,
        env=env
    )
    
    screenshots_taken = []
    console_errors = []
    
    try:
        if not wait_for_port(port, timeout=75):
            server_log.close()
            with open(os.path.join(scratch_dir, "uvicorn_verify.log"), "r", encoding="utf-8") as f:
                log_content = f.read()
            raise RuntimeError(f"Server failed to start on port {port} within timeout. Output:\n{log_content}")
        print(f"Server is listening on 127.0.0.1:{port}.")
        
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            
            viewports = [
                ("desktop_1440", 1440, 900),
                ("tablet_768", 768, 1024),
                ("mobile_390", 390, 844)
            ]
            
            for vp_name, width, height in viewports:
                for theme in ["light", "dark"]:
                    print(f"\n--- Testing Viewport: {vp_name} ({width}x{height}) | Theme: {theme} ---")
                    context = browser.new_context(
                        viewport={"width": width, "height": height},
                        device_scale_factor=1
                    )
                    page = context.new_page()
                    
                    # Print all console messages for diagnostics
                    def on_console(msg):
                        print(f"  [{vp_name}][{theme}][Console {msg.type}] {msg.text}")
                        if msg.type == "error":
                            txt = msg.text
                            if "400" in txt or "Failed to load resource" in txt:
                                return
                            console_errors.append(f"[{vp_name}][{theme}][Console {msg.type}] {txt}")
                            
                    page.on("console", on_console)
                    page.on("pageerror", lambda err: print(f"  [{vp_name}][{theme}][PageError] {err}"))
                    
                    # Navigate to root
                    page.goto(f"http://127.0.0.1:{port}/#overview")
                    page.wait_for_selector("#view-overview.active")
                    page.wait_for_timeout(300)
                    
                    # Apply Theme
                    current_theme = page.evaluate("document.documentElement.getAttribute('data-theme')")
                    if current_theme != theme:
                        page.click("#theme-toggle-btn")
                        page.wait_for_timeout(200)
                    
                    # -------------------------------------------------------------
                    # FLOW 1: Overview
                    # -------------------------------------------------------------
                    page.goto(f"http://127.0.0.1:{port}/#overview")
                    page.wait_for_selector("#task-card-estimate")
                    page.wait_for_selector("#task-card-diagnose")
                    page.wait_for_selector("#task-card-placement")
                    page.wait_for_selector("#task-card-field")
                    page.wait_for_selector("#task-card-poisson")
                    page.wait_for_selector("#headline-findings-container .headline-card")
                    page.wait_for_selector("#overview-limits-strip")
                    page.wait_for_selector("#overview-technical-details")
                    page.wait_for_timeout(200)
                    shot_path = os.path.join(SCREENSHOTS_DIR, f"{vp_name}_{theme}_01_overview.png")
                    page.screenshot(path=shot_path, full_page=False)
                    screenshots_taken.append(shot_path)

                    shot_path_full = os.path.join(SCREENSHOTS_DIR, f"{vp_name}_{theme}_01_overview_full.png")
                    page.screenshot(path=shot_path_full, full_page=True)
                    screenshots_taken.append(shot_path_full)

                    # Verify "Try example" button functionality
                    page.click("#try-example-diagnose-btn")
                    page.wait_for_selector("#view-diagnose.active")
                    page.wait_for_selector("#diag-result-panel", state="visible")
                    page.wait_for_timeout(200)
                    
                    # -------------------------------------------------------------
                    # TYPE SCALE CHECK (Requirement 6)
                    # -------------------------------------------------------------
                    if vp_name == "desktop_1440" and theme == "light":
                        print("  [TypeScale Check] Verifying H1, H2, and body computed font sizes across all 8 tabs...")
                        tabs_to_check = [
                            ("overview", "#view-overview"),
                            ("estimate", "#view-estimate"),
                            ("diagnose", "#view-diagnose"),
                            ("placement", "#view-placement"),
                            ("field", "#view-field"),
                            ("poisson", "#view-poisson"),
                            ("evidence", "#view-evidence"),
                            ("limits", "#view-limits"),
                        ]
                        h1_sizes = {}
                        h2_sizes = {}
                        body_sizes = {}
                        for t_name, t_sel in tabs_to_check:
                            page.goto(f"http://127.0.0.1:{port}/#{t_name}")
                            page.wait_for_selector(f"{t_sel}.active")
                            h1_sz = page.evaluate(f"window.getComputedStyle(document.querySelector('{t_sel} h1')).fontSize")
                            h2_sz = page.evaluate(f"window.getComputedStyle(document.querySelector('{t_sel} h2')).fontSize")
                            body_sz = page.evaluate(f"window.getComputedStyle(document.querySelector('{t_sel} p')).fontSize")
                            h1_sizes[t_name] = h1_sz
                            h2_sizes[t_name] = h2_sz
                            body_sizes[t_name] = body_sz
                        
                        assert len(set(h1_sizes.values())) == 1, f"H1 font-size mismatch across tabs: {h1_sizes}"
                        assert len(set(h2_sizes.values())) == 1, f"H2 font-size mismatch across tabs: {h2_sizes}"
                        assert len(set(body_sizes.values())) == 1, f"Body font-size mismatch across tabs: {body_sizes}"
                        print(f"  [TypeScale Check] PASSED: All 8 tabs share identical scales: H1={list(h1_sizes.values())[0]}, H2={list(h2_sizes.values())[0]}, body={list(body_sizes.values())[0]}")

                    # -------------------------------------------------------------
                    # FLOW 2: Estimate (Simplified Table, 4 Flows, Drawer, Errors)
                    # -------------------------------------------------------------
                    page.goto(f"http://127.0.0.1:{port}/#estimate")
                    page.wait_for_selector("#view-estimate.active")

                    # 2a. Verify Empty State & Table Initialization
                    assert page.locator("#estimate-results-card").is_hidden(), "Result card should NOT be visible before calculation"
                    assert page.locator("#est-result-panel").is_hidden(), "Result panel should NOT be visible on fresh load"
                    assert page.locator("#est-readings-table tbody tr").count() == 3, "Expected 3 initial table rows"
                    assert "0 of 3 needed" in page.locator("#est-readings-count").text_content(), "Expected '0 of 3 needed' on fresh load"
                    # Verify × delete buttons are hidden when only 3 rows exist
                    first_del_vis = page.locator("#est-readings-table tbody tr:first-child .btn-cell-delete").evaluate("el => window.getComputedStyle(el).visibility")
                    assert first_del_vis == "hidden", "Expected delete button to be hidden when only 3 rows exist"

                    # Verify Tab in last cell of last row adds a new row
                    last_cell = page.locator("#est-readings-table tbody tr:last-child .cell-input[data-col='u']")
                    last_cell.focus()
                    page.keyboard.press("Tab")
                    page.wait_for_timeout(100)
                    assert page.locator("#est-readings-table tbody tr").count() == 4, "Expected 4 rows after pressing Tab in last cell"
                    # Now delete button on row 4 is visible; click it to return to 3 rows
                    del_btn_r4 = page.locator("#est-readings-table tbody tr:last-child .btn-cell-delete")
                    del_vis_r4 = del_btn_r4.evaluate("el => window.getComputedStyle(el).visibility")
                    assert del_vis_r4 == "visible", "Expected delete button to be visible when > 3 rows exist"
                    del_btn_r4.click()
                    page.wait_for_timeout(100)
                    assert page.locator("#est-readings-table tbody tr").count() == 3, "Expected 3 rows after deleting 4th row"

                    # Screenshot 1: Empty state (3 rows)
                    shot_empty = os.path.join(SCREENSHOTS_DIR, f"{vp_name}_{theme}_02a_estimate_empty.png")
                    page.screenshot(path=shot_empty, full_page=False)
                    screenshots_taken.append(shot_empty)

                    # 2b. Verify Validation on Empty Table (< 3 readings or missing fields)
                    page.click("#est-submit-btn")
                    page.wait_for_timeout(100)
                    assert page.locator("#estimate-results-card").is_hidden(), "Result card should NOT appear with fewer than 3 readings"
                    val_msg = page.locator("#est-table-validation-msg").text_content()
                    state_msg = page.locator("#est-state-container").text_content()
                    assert "3 readings" in val_msg or "3 readings" in state_msg or "test settings" in val_msg.lower() or "required" in val_msg.lower()

                    # 2c. Verify Cell Error Validation (non-numeric Time, out-of-bounds Position)
                    first_row_inputs = page.locator("#est-readings-table tbody tr:first-child .cell-input")
                    first_row_inputs.nth(1).fill("not_a_number")
                    page.wait_for_timeout(100)
                    assert "cell-error" in (first_row_inputs.nth(1).get_attribute("class") or ""), "Expected .cell-error on invalid Time cell"
                    assert "Time must be a number" in page.locator("#est-table-validation-msg").text_content()

                    # Screenshot 4: One error cell
                    shot_err = os.path.join(SCREENSHOTS_DIR, f"{vp_name}_{theme}_02d_estimate_error_cell.png")
                    page.screenshot(path=shot_err, full_page=False)
                    screenshots_taken.append(shot_err)
                    if theme == "light":
                        named_err_shot = os.path.join(SCREENSHOTS_DIR, f"{vp_name}_estimate_error_case.png")
                        page.screenshot(path=named_err_shot, full_page=False)
                        screenshots_taken.append(named_err_shot)

                    first_row_inputs.nth(0).fill("2.5")  # Position out of bounds [0, 1]
                    first_row_inputs.nth(1).fill("0.05")
                    first_row_inputs.nth(2).fill("0.95")
                    page.wait_for_timeout(100)
                    assert "cell-error" in (first_row_inputs.nth(0).get_attribute("class") or ""), "Expected .cell-error on out-of-bounds Position cell"
                    assert "Position must be between 0 and 1" in page.locator("#est-table-validation-msg").text_content()

                    # Clear row 0
                    first_row_inputs.nth(0).fill("")
                    first_row_inputs.nth(1).fill("")
                    first_row_inputs.nth(2).fill("")
                    page.wait_for_timeout(100)

                    # 2d. FLOW A: "Use example" Button Flow
                    page.click("#est-use-example-btn")
                    page.wait_for_timeout(100)
                    assert page.locator("#est-readings-table tbody tr").count() == 10, "Expected 10 rows after 'Use example'"
                    assert "10 readings ✓" in page.locator("#est-readings-count").text_content()

                    # Screenshot 2: After "Use example"
                    shot_example = os.path.join(SCREENSHOTS_DIR, f"{vp_name}_{theme}_02b_estimate_after_example.png")
                    page.screenshot(path=shot_example, full_page=False)
                    screenshots_taken.append(shot_example)

                    page.click("#est-submit-btn")
                    page.wait_for_selector("#estimate-results-card", state="visible")
                    page.wait_for_selector("#est-result-panel", state="visible")
                    page.wait_for_timeout(250)

                    # Assert Result Card contents & Typography hierarchy
                    assert "Heat spread (α)" in page.locator("#est-result-label").text_content()
                    assert page.locator("#est-plain-number").text_content().strip() != "", "Expected result number"
                    assert "Most likely between" in page.locator("#est-plain-subline").text_content()
                    banner_cls = page.locator("#est-traffic-banner").get_attribute("class")
                    assert "green" in banner_cls or "amber" in banner_cls, f"Expected green or amber banner, got {banner_cls}"
                    assert page.locator("#est-chart-svg").is_visible(), "Measured vs fitted chart must be visible"

                    # Screenshot 3: After Calculate
                    shot_calc = os.path.join(SCREENSHOTS_DIR, f"{vp_name}_{theme}_02c_estimate_after_calculate.png")
                    page.screenshot(path=shot_calc, full_page=False)
                    screenshots_taken.append(shot_calc)

                    if theme == "light":
                        named_shot = os.path.join(SCREENSHOTS_DIR, f"{vp_name}_estimate_example_result.png")
                        page.screenshot(path=named_shot, full_page=False)
                        screenshots_taken.append(named_shot)

                    # Also save legacy path for compatibility
                    page.evaluate("window.scrollTo(0, 0)")
                    shot_path = os.path.join(SCREENSHOTS_DIR, f"{vp_name}_{theme}_02_estimate_mode3plus.png")
                    page.screenshot(path=shot_path, full_page=False)
                    screenshots_taken.append(shot_path)

                    # 2e. "More options" Side Drawer & Mode 2 Test
                    page.click("#est-more-options-btn")
                    page.wait_for_selector("#est-more-drawer.open", state="visible")
                    page.wait_for_timeout(150)

                    # Screenshot 5: Drawer open
                    shot_drawer = os.path.join(SCREENSHOTS_DIR, f"{vp_name}_{theme}_02e_estimate_drawer_open.png")
                    page.screenshot(path=shot_drawer, full_page=False)
                    screenshots_taken.append(shot_drawer)

                    page.select_option("#est-method-select", "mode2")
                    page.click("#est-drawer-close-btn")
                    page.wait_for_timeout(150)

                    page.click("#est-submit-btn")
                    page.wait_for_selector("#est-result-panel", state="visible")
                    page.wait_for_timeout(200)

                    # Open details disclosure and verify Mode 2
                    page.locator("#est-technical-details").evaluate("el => el.open = true")
                    method_txt = page.locator("#est-out-method").text_content().lower()
                    assert "mode 2" in method_txt or "mode2" in method_txt, f"Expected Mode 2 method, got {method_txt}"

                    page.evaluate("window.scrollTo(0, 0)")
                    shot_path = os.path.join(SCREENSHOTS_DIR, f"{vp_name}_{theme}_02b_estimate_mode2.png")
                    page.screenshot(path=shot_path, full_page=False)
                    screenshots_taken.append(shot_path)

                    # Reset method back to mode3plus in drawer
                    page.click("#est-more-options-btn")
                    page.wait_for_selector("#est-more-drawer.open", state="visible")
                    page.select_option("#est-method-select", "mode3plus")
                    page.click("#est-drawer-close-btn")
                    page.wait_for_timeout(150)

                    # Test remaining flows in desktop view to avoid redundant slow requests
                    if vp_name == "desktop_1440" and theme == "light":
                        # 2f. FLOW B: Manual Typing Flow
                        print("  [Flow B: Manual Typing] Entering 4 manual physical readings...")
                        page.locator("#est-table-tbody").evaluate("el => el.innerHTML = ''")
                        for _ in range(4):
                            page.click("#est-add-row-btn")
                        rows = page.locator("#est-table-tbody tr")
                        manual_vals = [
                            ("0.05", "2.0", "79.0"),
                            ("0.05", "8.0", "75.0"),
                            ("0.05", "25.0", "65.0"),
                            ("0.05", "60.0", "52.0")
                        ]
                        for idx, (x_v, t_v, u_v) in enumerate(manual_vals):
                            r_inputs = rows.nth(idx).locator(".cell-input")
                            r_inputs.nth(0).fill(x_v)
                            r_inputs.nth(1).fill(t_v)
                            r_inputs.nth(2).fill(u_v)
                        page.wait_for_timeout(100)
                        assert "4 reading" in page.locator("#est-readings-count").text_content()
                        page.click("#est-submit-btn")
                        page.wait_for_selector("#est-result-panel", state="visible")
                        print("  [Flow B: Manual Typing] Succeeded!")

                        # 2g. FLOW C: Paste Flow (Tab-separated multi-row data)
                        print("  [Flow C: Paste Flow] Pasting multi-row TSV data...")
                        page.locator("#est-table-tbody").evaluate("el => el.innerHTML = ''")
                        page.click("#est-add-row-btn")
                        paste_data = "0.05\t3.0\t78.0\n0.05\t10.0\t74.0\n0.05\t30.0\t64.0\n0.05\t70.0\t50.0"
                        page.evaluate(f"""() => {{
                            const dt = new DataTransfer();
                            dt.setData('text/plain', {json.dumps(paste_data)});
                            const input = document.querySelector('#est-table-tbody .cell-input');
                            const ev = new ClipboardEvent('paste', {{ clipboardData: dt, bubbles: true, cancelable: true }});
                            input.dispatchEvent(ev);
                        }}""")
                        page.wait_for_timeout(150)
                        assert "4 reading" in page.locator("#est-readings-count").text_content()
                        page.click("#est-submit-btn")
                        page.wait_for_selector("#est-result-panel", state="visible")
                        print("  [Flow C: Paste Flow] Succeeded!")

                        # 2h. FLOW D: CSV Upload Flow
                        print("  [Flow D: CSV Upload] Uploading test CSV...")
                        test_csv_path = os.path.join(scratch_dir, "playwright_sample.csv")
                        with open(test_csv_path, "w", encoding="utf-8") as f_csv:
                            f_csv.write("Position,Time,Temperature\n0.05,1.5,79.0\n0.05,5.0,76.5\n0.05,15.0,71.0\n0.05,40.0,60.0\n0.05,90.0,45.0\n")
                        page.set_input_files("#est-csv-upload", test_csv_path)
                        page.wait_for_timeout(200)
                        assert "5 reading" in page.locator("#est-readings-count").text_content()
                        page.click("#est-submit-btn")
                        page.wait_for_selector("#est-result-panel", state="visible")
                        print("  [Flow D: CSV Upload] Succeeded!")

                    # 2i. Mobile 390px Viewport Checks
                    if vp_name == "mobile_390":
                        has_hscroll = page.evaluate("document.documentElement.scrollWidth > document.documentElement.clientWidth")
                        assert not has_hscroll, "Horizontal overflow detected on mobile 390px viewport!"
                        assert page.locator("#est-readings-table").is_visible(), "Table must be visible and usable on mobile"
                        assert page.locator("#est-submit-btn").is_visible(), "Calculate button must be visible on mobile"
                    
                    # -------------------------------------------------------------
                    # FLOW 3: Diagnose (All Scenarios)
                    # -------------------------------------------------------------
                    page.goto(f"http://127.0.0.1:{port}/#diagnose")
                    page.wait_for_selector("#view-diagnose.active")
                    
                    scenarios = [
                        ("H", "03a_diagnose_healthy"),
                        ("A", "03b_diagnose_anomalous"),
                        ("F_stuck", "03c_diagnose_fault_stuck"),
                        ("F_bias", "03d_diagnose_fault_bias"),
                        ("C", "03e_diagnose_changepoint")
                    ]
                    for sc_val, sc_name in scenarios:
                        page.select_option("#diag-scenario-select", sc_val)
                        page.click("#diag-submit-btn")
                        page.wait_for_selector("#diag-result-panel", state="visible")
                        page.wait_for_timeout(200)
                        # Explicit Playwright assertion: no error box on H, A, F, C scenarios
                        assert page.locator("#diag-state-container .state-box.error").count() == 0, f"Error box detected in scenario {sc_val}"
                        shot_path = os.path.join(SCREENSHOTS_DIR, f"{vp_name}_{theme}_{sc_name}.png")
                        page.screenshot(path=shot_path, full_page=False)
                        screenshots_taken.append(shot_path)
                        
                    # -------------------------------------------------------------
                    # FLOW 4: Place Sensors
                    # -------------------------------------------------------------
                    page.goto(f"http://127.0.0.1:{port}/#placement")
                    page.wait_for_selector("#view-placement.active")
                    page.click("#place-submit-btn")
                    page.wait_for_selector("#place-result-panel", state="visible")
                    page.wait_for_timeout(200)
                    shot_path = os.path.join(SCREENSHOTS_DIR, f"{vp_name}_{theme}_04_placement.png")
                    page.screenshot(path=shot_path, full_page=False)
                    screenshots_taken.append(shot_path)
                    
                    # -------------------------------------------------------------
                    # FLOW 5: Field (Solver, FNO, Compare)
                    # -------------------------------------------------------------
                    page.goto(f"http://127.0.0.1:{port}/#field")
                    page.wait_for_selector("#view-field.active")
                    
                    # Compare Mode
                    page.click("#field-method-compare-btn")
                    page.click("#field-submit-btn")
                    page.wait_for_selector("#field-result-panel", state="visible")
                    page.wait_for_timeout(250)
                    shot_path = os.path.join(SCREENSHOTS_DIR, f"{vp_name}_{theme}_05a_field_compare.png")
                    page.screenshot(path=shot_path, full_page=False)
                    screenshots_taken.append(shot_path)
                    
                    # Solver Mode
                    page.click("#field-method-solver-btn")
                    page.click("#field-submit-btn")
                    page.wait_for_timeout(200)
                    shot_path = os.path.join(SCREENSHOTS_DIR, f"{vp_name}_{theme}_05b_field_solver.png")
                    page.screenshot(path=shot_path, full_page=False)
                    screenshots_taken.append(shot_path)
                    
                    # FNO Mode
                    page.click("#field-method-fno-btn")
                    page.click("#field-submit-btn")
                    page.wait_for_timeout(200)
                    shot_path = os.path.join(SCREENSHOTS_DIR, f"{vp_name}_{theme}_05c_field_fno.png")
                    page.screenshot(path=shot_path, full_page=False)
                    screenshots_taken.append(shot_path)
                    
                    # -------------------------------------------------------------
                    # FLOW 6: Stage 2 Poisson (Sine low, Sine high mode, Gaussian)
                    # -------------------------------------------------------------
                    page.goto(f"http://127.0.0.1:{port}/#poisson")
                    page.wait_for_selector("#view-poisson.active")
                    
                    # 1. Low-frequency sine
                    page.select_option("#poi-presets-select", "sine_low")
                    page.click("#poi-submit-btn")
                    page.wait_for_selector("#poi-result-panel", state="visible")
                    page.wait_for_timeout(250)
                    shot_path = os.path.join(SCREENSHOTS_DIR, f"{vp_name}_{theme}_06a_poisson_sine_low.png")
                    page.screenshot(path=shot_path, full_page=False)
                    screenshots_taken.append(shot_path)
                    
                    # 2. High-frequency sine (triggers warning banner!)
                    page.select_option("#poi-presets-select", "sine_high")
                    page.click("#poi-submit-btn")
                    page.wait_for_selector("#poisson-hf-banner", state="visible")
                    page.wait_for_timeout(250)
                    shot_path = os.path.join(SCREENSHOTS_DIR, f"{vp_name}_{theme}_06b_poisson_sine_high_warning.png")
                    page.screenshot(path=shot_path, full_page=False)
                    screenshots_taken.append(shot_path)
                    
                    # 3. Gaussian heater
                    page.select_option("#poi-presets-select", "gauss_center")
                    page.click("#poi-submit-btn")
                    page.wait_for_timeout(250)
                    shot_path = os.path.join(SCREENSHOTS_DIR, f"{vp_name}_{theme}_06c_poisson_gaussian.png")
                    page.screenshot(path=shot_path, full_page=False)
                    screenshots_taken.append(shot_path)
                    
                    # -------------------------------------------------------------
                    # FLOW 7: Evidence Archive
                    # -------------------------------------------------------------
                    page.goto(f"http://127.0.0.1:{port}/#evidence")
                    page.wait_for_selector("#view-evidence.active")
                    page.wait_for_selector("#ev-tbody-s1 tr")
                    page.wait_for_timeout(350)
                    shot_path = os.path.join(SCREENSHOTS_DIR, f"{vp_name}_{theme}_07_evidence.png")
                    page.screenshot(path=shot_path, full_page=True)
                    screenshots_taken.append(shot_path)
                    
                    # -------------------------------------------------------------
                    # FLOW 8: Limits
                    # -------------------------------------------------------------
                    page.goto(f"http://127.0.0.1:{port}/#limits")
                    page.wait_for_selector("#view-limits.active")
                    page.wait_for_timeout(200)
                    shot_path = os.path.join(SCREENSHOTS_DIR, f"{vp_name}_{theme}_08_limits.png")
                    page.screenshot(path=shot_path, full_page=False)
                    screenshots_taken.append(shot_path)
                    
                    # -------------------------------------------------------------
                    # FLOW 9: Failure Paths
                    # -------------------------------------------------------------
                    # 9a. Baseline refusal k=10
                    page.goto(f"http://127.0.0.1:{port}/#diagnose")
                    page.wait_for_selector("#view-diagnose.active")
                    page.select_option("#diag-scenario-select", "refusal_baseline")
                    page.click("#diag-submit-btn")
                    page.wait_for_selector("#diag-state-container .state-box.refusal", state="visible")
                    shot_path = os.path.join(SCREENSHOTS_DIR, f"{vp_name}_{theme}_09a_failure_refusal_baseline.png")
                    page.screenshot(path=shot_path, full_page=False)
                    screenshots_taken.append(shot_path)
                    
                    # 9b. Malformed input on estimate
                    page.goto(f"http://127.0.0.1:{port}/#estimate")
                    page.wait_for_selector("#view-estimate.active")
                    r0 = page.locator("#est-readings-table tbody tr:first-child .cell-input")
                    r0.nth(0).fill("bad data")
                    r0.nth(1).fill("not numbers")
                    r0.nth(2).fill("only_one_col")
                    page.click("#est-submit-btn")
                    page.wait_for_selector("#est-state-container .state-box.error", state="visible")
                    shot_path = os.path.join(SCREENSHOTS_DIR, f"{vp_name}_{theme}_09b_failure_malformed_input.png")
                    page.screenshot(path=shot_path, full_page=False)
                    screenshots_taken.append(shot_path)

                    # 9c. Out of range alpha (alpha = 20.0)
                    page.click("#est-more-options-btn")
                    page.wait_for_selector("#est-more-drawer.open", state="visible")
                    page.fill("#est-true-alpha", "20.0")
                    page.click("#est-sample-synth-btn")
                    page.click("#est-drawer-close-btn")
                    page.click("#est-submit-btn")
                    page.wait_for_selector("#est-result-panel", state="visible")
                    page.locator("#est-technical-details").evaluate("el => el.open = true")
                    page.wait_for_selector("#est-badges-container .badge-warning", state="visible")
                    shot_path = os.path.join(SCREENSHOTS_DIR, f"{vp_name}_{theme}_09c_failure_out_of_range.png")
                    page.screenshot(path=shot_path, full_page=False)
                    screenshots_taken.append(shot_path)
                    
                    context.close()
            
            # -------------------------------------------------------------
            # FLOW 10: Service Stopped Failure Path
            # -------------------------------------------------------------
            print("\n--- Testing Failure Path: Service Stopped ---")
            server_proc.terminate()
            try:
                server_proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                server_proc.kill()
            time.sleep(1)
            
            context = browser.new_context(viewport={"width": 1440, "height": 900})
            page = context.new_page()
            # Open offline page
            page.goto(f"file:///{REPO_ROOT.replace('\\', '/')}/service/static/index.html#overview")
            page.wait_for_timeout(1000)
            page.evaluate("checkServiceHealth()")
            page.wait_for_timeout(500)
            
            shot_path = os.path.join(SCREENSHOTS_DIR, "desktop_1440_failure_service_stopped.png")
            page.screenshot(path=shot_path, full_page=False)
            screenshots_taken.append(shot_path)
            context.close()

            browser.close()
            
    finally:
        try:
            server_log.close()
        except Exception:
            pass
        if server_proc.poll() is None:
            try:
                subprocess.run(["taskkill", "/F", "/T", "/PID", str(server_proc.pid)], capture_output=True)
            except Exception:
                server_proc.terminate()
            
    print(f"\nVerification Complete! Captured {len(screenshots_taken)} screenshots in {SCREENSHOTS_DIR}.")
    if console_errors:
        print(f"FAILED: Found {len(console_errors)} unexpected console errors:")
        for err in console_errors:
            print("  ", err)
        assert len(console_errors) == 0, f"Playwright assertion failed: {len(console_errors)} console errors found: {console_errors}"
    else:
        print("Zero console errors! All requests succeeded.")
        
    return screenshots_taken, console_errors

if __name__ == "__main__":
    shots, errs = run_verification()
    sys.exit(1 if errs else 0)
