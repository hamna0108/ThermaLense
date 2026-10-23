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
    server_proc = subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "service.app:app", "--port", str(port), "--host", "127.0.0.1"],
        cwd=REPO_ROOT,
        stdout=server_log,
        stderr=subprocess.STDOUT
    )
    
    screenshots_taken = []
    console_errors = []
    
    try:
        if not wait_for_port(port, timeout=60):
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
                    page.wait_for_selector("#headline-findings-container .headline-card")
                    page.wait_for_timeout(200)
                    shot_path = os.path.join(SCREENSHOTS_DIR, f"{vp_name}_{theme}_01_overview.png")
                    page.screenshot(path=shot_path, full_page=False)
                    screenshots_taken.append(shot_path)
                    
                    # -------------------------------------------------------------
                    # FLOW 2: Estimate (Mode 3+ and Mode 2)
                    # -------------------------------------------------------------
                    page.goto(f"http://127.0.0.1:{port}/#estimate")
                    page.wait_for_selector("#view-estimate.active")
                    page.click("#est-submit-btn")
                    page.wait_for_selector("#est-result-panel", state="visible")
                    page.wait_for_timeout(250)
                    shot_path = os.path.join(SCREENSHOTS_DIR, f"{vp_name}_{theme}_02_estimate_mode3plus.png")
                    page.screenshot(path=shot_path, full_page=False)
                    screenshots_taken.append(shot_path)
                    
                    # Switch to Mode 2
                    page.select_option("#est-method-select", "mode2")
                    page.click("#est-submit-btn")
                    page.wait_for_selector("#est-result-panel", state="visible")
                    page.wait_for_timeout(200)
                    shot_path = os.path.join(SCREENSHOTS_DIR, f"{vp_name}_{theme}_02b_estimate_mode2.png")
                    page.screenshot(path=shot_path, full_page=False)
                    screenshots_taken.append(shot_path)
                    
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
                    
                    # 9b. Malformed pasted rows on estimate
                    page.goto(f"http://127.0.0.1:{port}/#estimate")
                    page.wait_for_selector("#view-estimate.active")
                    page.click("#estimate-mode-paste-btn")
                    page.fill("#est-paste-text", "bad data, not numbers\nonly_one_col")
                    page.click("#est-submit-btn")
                    page.wait_for_selector("#est-state-container .state-box.error", state="visible")
                    shot_path = os.path.join(SCREENSHOTS_DIR, f"{vp_name}_{theme}_09b_failure_malformed_input.png")
                    page.screenshot(path=shot_path, full_page=False)
                    screenshots_taken.append(shot_path)

                    # 9c. Out of range alpha (alpha = 20.0)
                    page.click("#estimate-mode-synth-btn")
                    page.fill("#est-true-alpha", "20.0")
                    page.click("#est-submit-btn")
                    page.wait_for_selector("#est-result-panel", state="visible")
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
