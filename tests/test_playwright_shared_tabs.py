"""Playwright End-to-End Suite for Shared Browser State and Tab Hand-Offs.

Verifies:
1. Shared "My readings": Estimate "Your readings" and Diagnose "The test to check"
   are the exact same data, syncing live bidirectionally.
2. Hand-off button "Use these times in my readings" (Place Sensors -> Estimate).
3. Hand-off button "Check this data for problems" (Estimate -> Diagnose).
4. Hand-off button "Estimate the heat spread" (Diagnose Normal -> Estimate).
5. Hand-off button "Estimate without sensor k" (Diagnose Fault -> Estimate with row removed & Undo).
6. Hand-off button "See the temperature map for this value" (Estimate -> Field with alpha filled).
7. Persistence across reload and tab switches with "Clear my data" button.
8. Zero console errors throughout the entire flow.
9. Screenshots captured at 1440x900 and 390x844 viewports.
"""

import os
import sys
import time
import socket
import shutil
import subprocess
import pytest
from playwright.sync_api import sync_playwright

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCREENSHOTS_DIR = os.path.join(REPO_ROOT, "reports", "screenshots")
os.makedirs(SCREENSHOTS_DIR, exist_ok=True)

ARTIFACT_DIR = r"C:\Users\HP\.gemini\antigravity-ide\brain\961a9ffe-e155-4ee2-974a-07dafb79184f"

def find_free_port():
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(('', 0))
        return s.getsockname()[1]

def wait_for_port(port, timeout=30):
    start = time.time()
    while time.time() - start < timeout:
        try:
            with socket.create_connection(('127.0.0.1', port), timeout=1):
                return True
        except (ConnectionRefusedError, OSError):
            time.sleep(0.5)
    return False

@pytest.fixture(scope="module")
def live_server():
    port = find_free_port()
    env = os.environ.copy()
    env["PYTHONUNBUFFERED"] = "1"
    proc = subprocess.Popen(
        [sys.executable, "-u", "-m", "uvicorn", "service.app:app", "--port", str(port), "--host", "127.0.0.1"],
        cwd=REPO_ROOT,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        env=env
    )
    if not wait_for_port(port, timeout=60):
        proc.kill()
        out, _ = proc.communicate()
        raise RuntimeError(f"Server failed to start on port {port}. Output:\n{out.decode('utf-8', errors='replace')}")
    import threading
    def drain_pipe():
        try:
            for _ in iter(proc.stdout.readline, b''):
                pass
        except Exception:
            pass
    t = threading.Thread(target=drain_pipe, daemon=True)
    t.start()
    yield f"http://127.0.0.1:{port}"
    proc.terminate()
    try:
        proc.wait(timeout=5)
    except subprocess.TimeoutExpired:
        proc.kill()

def save_and_copy_screenshot(page, filename):
    dest = os.path.join(SCREENSHOTS_DIR, filename)
    page.screenshot(path=dest, full_page=True)
    if os.path.isdir(ARTIFACT_DIR):
        try:
            shutil.copy(dest, os.path.join(ARTIFACT_DIR, filename))
        except Exception:
            pass
    return dest

def test_full_handoff_flow_1440(live_server):
    """Full cross-tab handoff flow at 1440x900 desktop viewport."""
    console_errors = []

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(viewport={"width": 1440, "height": 900})
        page = context.new_page()

        page.on("console", lambda msg: console_errors.append(f"CONSOLE {msg.type}: {msg.text}") if msg.type in ["error"] else None)
        page.on("pageerror", lambda err: console_errors.append(f"PAGEERROR: {err}"))

        # ------------------------------------------------------------------
        # Step 1: Place Sensors -> "Use these times in my readings" -> Estimate
        # ------------------------------------------------------------------
        page.goto(f"{live_server}/#placement")
        page.wait_for_selector("#place-submit-btn", state="visible")
        page.click("#place-submit-btn")
        page.wait_for_selector("#place-result-panel", state="visible", timeout=15000)

        # Click "Use these times in my readings"
        page.wait_for_selector("#place-use-times-btn", state="visible")
        page.click("#place-use-times-btn")

        # Verify routed to #estimate
        assert "#estimate" in page.url
        page.wait_for_selector("#est-table-tbody", state="visible")

        # Verify time column has values from placement schedule
        first_time_input = page.locator("#est-table-tbody tr:nth-child(1) input[data-col='t']")
        assert float(first_time_input.input_value()) > 0

        # Now click "Use example" on Estimate
        page.click("#est-use-example-btn")
        time.sleep(0.3)

        # Check Estimate has 10 rows
        est_rows = page.locator("#est-table-tbody tr")
        assert est_rows.count() == 10

        # Check that Diagnose "The test to check" table already has 10 rows synced live!
        diag_rows = page.locator("#diag-test-table-tbody tr")
        assert diag_rows.count() == 10
        assert page.locator("#diag-test-count").inner_text() == "10 readings ✓"

        # Calculate Estimate
        page.click("#est-submit-btn")
        page.wait_for_selector("#est-result-panel", state="visible", timeout=15000)

        # Verify Hand-off buttons exist on Estimate result
        page.wait_for_selector("#est-goto-diagnose-btn", state="visible")
        page.wait_for_selector("#est-goto-field-btn", state="visible")

        save_and_copy_screenshot(page, "handoff_1440_step1_estimate.png")

        # ------------------------------------------------------------------
        # Step 2: Estimate -> "Check this data for problems" -> Diagnose
        # ------------------------------------------------------------------
        page.click("#est-goto-diagnose-btn")
        assert "#diagnose" in page.url

        # Diagnose test table has the identical 10 rows
        assert page.locator("#diag-test-table-tbody tr").count() == 10

        # Add reference data via Diagnose "Use example"
        page.click("#diag-use-example-btn")
        time.sleep(0.3)

        # Check baseline table has 20 rows
        assert page.locator("#diag-base-table-tbody tr").count() == 20

        # Run diagnosis (Normal baseline)
        page.click("#diag-submit-btn")
        page.wait_for_selector("#diag-result-panel", state="visible", timeout=15000)

        # Verify Normal verdict
        assert "Everything looks normal." in page.locator("#diag-traffic-title").inner_text()

        # Verify "Estimate the heat spread" button is visible, Faulty button hidden
        page.wait_for_selector("#diag-goto-estimate-btn", state="visible")
        assert not page.locator("#diag-goto-estimate-without-fault-btn").is_visible()

        save_and_copy_screenshot(page, "handoff_1440_step2_diagnose_normal.png")

        # Click "Estimate the heat spread" -> returns to Estimate
        page.click("#diag-goto-estimate-btn")
        assert "#estimate" in page.url

        # ------------------------------------------------------------------
        # Step 3: Diagnose Faulty Sensor -> "Estimate without sensor k" -> Undo
        # ------------------------------------------------------------------
        page.goto(f"{live_server}/#diagnose")
        page.wait_for_selector("#diag-more-options-btn", state="visible")
        page.click("#diag-more-options-btn")
        page.wait_for_selector("#diag-more-drawer.open", state="visible")
        page.select_option("#diag-scenario-select", "F_stuck")
        page.click("#diag-load-demo-btn")
        time.sleep(0.3)

        # Run diagnosis on faulty sensor
        page.click("#diag-submit-btn")
        page.wait_for_selector("#diag-result-panel", state="visible", timeout=15000)

        # Verdict: Faulty sensor
        verdict_text = page.locator("#diag-traffic-title").inner_text()
        assert "Reading #3 looks faulty (position 0.03 m, time 4.6 s)" in verdict_text

        # Verify "Estimate without reading 3" button is visible
        fault_handoff_btn = page.locator("#diag-goto-estimate-without-fault-btn")
        page.wait_for_selector("#diag-goto-estimate-without-fault-btn", state="visible")
        assert fault_handoff_btn.inner_text() == "Estimate without reading 3"

        save_and_copy_screenshot(page, "handoff_1440_step3_diagnose_fault.png")

        # Click "Estimate without reading 3"
        fault_handoff_btn.click()
        assert "#estimate" in page.url

        # Verify note is visible on Estimate tab
        page.wait_for_selector("#est-removed-sensor-note", state="visible")
        assert "Reading #3 was removed from these readings." in page.locator("#est-removed-sensor-text").inner_text()

        # Verify reading row was removed (9 rows remain)
        assert page.locator("#est-table-tbody tr").count() == 9
        assert page.locator("#diag-test-table-tbody tr").count() == 9

        # Click "Undo"
        page.click("#est-undo-remove-sensor-btn")
        time.sleep(0.3)

        # Verify note is hidden and 10 rows restored
        assert not page.locator("#est-removed-sensor-note").is_visible()
        assert page.locator("#est-table-tbody tr").count() == 10
        assert page.locator("#diag-test-table-tbody tr").count() == 10

        save_and_copy_screenshot(page, "handoff_1440_step3_undo_restored.png")

        # ------------------------------------------------------------------
        # Step 4: Estimate -> "See the temperature map for this value" -> Field
        # ------------------------------------------------------------------
        page.click("#est-submit-btn")
        page.wait_for_selector("#est-result-panel", state="visible", timeout=15000)

        page.click("#est-goto-field-btn")
        assert "#field" in page.url

        # Field tab should have prefilled alpha (~0.100)
        field_alpha_val = float(page.locator("#field-alpha").input_value())
        assert abs(field_alpha_val - 0.100) < 0.05

        # Compute field
        page.click("#field-submit-btn")
        page.wait_for_selector("#field-result-panel", state="visible", timeout=15000)
        # Open heatmap disclosure before waiting for canvas
        page.click("#field-heatmap-disclosure summary")
        page.wait_for_selector("#field-canvas", state="visible")

        save_and_copy_screenshot(page, "handoff_1440_step4_field.png")

        # ------------------------------------------------------------------
        # Step 5: Persistence Across Reloads and "Clear my data"
        # ------------------------------------------------------------------
        # Verify localStorage has the readings
        stored = page.evaluate("() => localStorage.getItem('thermalens_shared_readings')")
        assert stored is not None and len(stored) > 20

        # Navigate to #estimate and reload page, checking readings still present
        page.goto(f"{live_server}/#estimate")
        page.reload()
        page.wait_for_selector("#est-table-tbody", state="visible")
        assert page.locator("#est-table-tbody tr").count() == 10
        assert page.locator("#diag-test-table-tbody tr").count() == 10

        # Click "Clear my data"
        page.click("#est-clear-data-btn")
        time.sleep(0.3)

        # Both tables now have 3 empty rows
        assert page.locator("#est-table-tbody tr").count() == 3
        assert page.locator("#diag-test-table-tbody tr").count() == 3
        assert page.locator("#est-readings-count").inner_text() == "0 of 3 needed"
        assert page.locator("#diag-test-count").inner_text() == "0 of 3 needed"

        # LocalStorage cleared
        stored_after_clear = page.evaluate("() => localStorage.getItem('thermalens_shared_readings')")
        assert stored_after_clear is None

        browser.close()

    assert len(console_errors) == 0, f"Encountered browser console errors: {console_errors}"

def test_full_handoff_flow_390(live_server):
    """Mobile 390x844 responsive verification with zero console errors."""
    console_errors = []

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(viewport={"width": 390, "height": 844})
        page = context.new_page()

        page.on("console", lambda msg: console_errors.append(f"CONSOLE {msg.type}: {msg.text}") if msg.type in ["error"] else None)
        page.on("pageerror", lambda err: console_errors.append(f"PAGEERROR: {err}"))

        # Step 1: Placement mobile
        page.goto(f"{live_server}/#placement")
        page.wait_for_selector("#place-submit-btn", state="visible")
        page.click("#place-submit-btn")
        page.wait_for_selector("#place-result-panel", state="visible", timeout=15000)
        save_and_copy_screenshot(page, "handoff_390_step1_placement.png")

        page.click("#place-use-times-btn")
        assert "#estimate" in page.url

        # Step 2: Estimate mobile
        page.click("#est-use-example-btn")
        page.click("#est-submit-btn")
        page.wait_for_selector("#est-result-panel", state="visible", timeout=15000)
        save_and_copy_screenshot(page, "handoff_390_step2_estimate.png")

        # Step 3: Diagnose mobile
        page.click("#est-goto-diagnose-btn")
        assert "#diagnose" in page.url
        page.click("#diag-use-example-btn")
        page.click("#diag-submit-btn")
        page.wait_for_selector("#diag-result-panel", state="visible", timeout=15000)
        save_and_copy_screenshot(page, "handoff_390_step3_diagnose.png")

        # Step 4: Field mobile
        page.goto(f"{live_server}/#field")
        page.wait_for_selector("#field-submit-btn", state="visible")
        page.click("#field-submit-btn")
        page.wait_for_selector("#field-result-panel", state="visible", timeout=15000)
        save_and_copy_screenshot(page, "handoff_390_step4_field.png")

        browser.close()

    assert len(console_errors) == 0, f"Mobile encountered console errors: {console_errors}"
