"""Playwright End-to-End Test Suite for Cross-Check Between Estimate and Diagnose.

Tests the 3 required cross-check banner cases:
1. Both green:
   "Estimate and Diagnose agree: the readings fit the heat model and match your healthy reference."
2. Estimate green, Diagnose flags:
   "The readings fit a heat curve, but they differ from your healthy reference (reading #3 looks faulty). The estimate may be less reliable. Try Estimate without reading 3."
   Also verifies Diagnose "Show details" line:
   "Estimate can still pass because it only checks that a smooth heat curve fits; Diagnose compares against your healthy reference."
3. Estimate flagged, Diagnose green:
   "The readings match your reference but do not fit the heat model. Check your setup values (length, duration, temperatures)."
"""

import os
import sys
import time
import socket
import subprocess
import pytest
from playwright.sync_api import sync_playwright

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

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
    """Start the uvicorn service in a background process with stdout draining."""
    port = find_free_port()
    env = os.environ.copy()
    env["PYTHONUNBUFFERED"] = "1"
    proc = subprocess.Popen(
        [sys.executable, "-u", "-m", "uvicorn", "service.app:app", "--port", str(port), "--host", "127.0.0.1"],
        cwd=REPO_ROOT,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        env=env,
        text=True,
        bufsize=1
    )

    import threading
    def drain_pipe():
        try:
            for line in iter(proc.stdout.readline, ''):
                if not line:
                    break
        except Exception:
            pass

    drain_thread = threading.Thread(target=drain_pipe, daemon=True)
    drain_thread.start()

    assert wait_for_port(port, timeout=120), "Server failed to start in 120s"
    yield f"http://127.0.0.1:{port}"

    proc.terminate()
    try:
        proc.wait(timeout=3)
    except subprocess.TimeoutExpired:
        proc.kill()

def test_crosscheck_case1_both_green(live_server):
    """Case 1: Default example readings fit heat model and conform to healthy baseline."""
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 1440, "height": 900})

        # 1. Load Estimate and populate default example data (seed 0)
        page.goto(f"{live_server}/#estimate")
        page.wait_for_selector("#est-use-example-btn", state="visible")
        page.click("#est-use-example-btn")
        time.sleep(0.3)

        # Select default steel bar profile if not already selected
        page.select_option("#est-profile-select", value="00000000-0000-4000-8000-000000000001")
        time.sleep(0.3)

        # Click calculate on Estimate
        page.click("#est-submit-btn")
        page.wait_for_selector("#est-result-panel", state="visible", timeout=15000)

        # Verify Cross-Check banner is removed from Estimate view completely
        assert page.locator("#est-crosscheck-banner").count() == 0
        assert page.locator("#est-goto-diagnose-btn").is_visible()

        # 2. Switch to Diagnose
        page.goto(f"{live_server}/#diagnose")
        page.wait_for_selector("#diag-submit-btn", state="visible")
        page.click("#diag-submit-btn")
        page.wait_for_selector("#diag-result-panel", state="visible", timeout=15000)

        # Verify Diagnose Cross-Check banner is visible
        page.wait_for_selector("#diag-crosscheck-banner", state="visible", timeout=5000)
        diag_banner = page.locator("#diag-crosscheck-banner")
        assert "green" in diag_banner.get_attribute("class")
        diag_text = page.locator("#diag-crosscheck-text").inner_text().strip()
        expected_msg = "Estimate and Diagnose agree: the readings fit the heat model and match your healthy reference."
        assert expected_msg in diag_text

        # In Show details, the flagged note should NOT be displayed
        assert not page.locator("#diag-details-crosscheck-note").is_visible()

        browser.close()

def test_crosscheck_case2_estimate_green_diagnose_flags(live_server):
    """Case 2: Readings fit smooth curve but Diagnose flags sensor fault (F on reading #3)."""
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 1440, "height": 900})

        # 1. Load Diagnose and select default bar profile
        page.goto(f"{live_server}/#diagnose")
        page.wait_for_selector("#diag-profile-select", state="visible")
        page.select_option("#diag-profile-select", value="00000000-0000-4000-8000-000000000001")
        time.sleep(0.3)

        # Click Use example to populate 10 operational readings
        page.click("#diag-use-example-btn")
        time.sleep(0.3)

        # Populate with verified readings (seed 3 layout where reading #3 at index 3 has an isolated offset:
        # Estimate chi2/dof = 1.685 < 1.88 -> Green/Trustworthy, Diagnose BIC flags F on reading #3)
        verified_readings = [
            ("0.03", "1.0", "67.61"),
            ("0.05", "1.67", "79.30"),
            ("0.07", "2.78", "67.49"),
            ("0.03", "4.64", "68.03"),  # Reading #3 (index 3)
            ("0.05", "7.74", "75.54"),
            ("0.07", "12.92", "62.89"),
            ("0.03", "21.54", "59.61"),
            ("0.05", "35.94", "62.26"),
            ("0.07", "59.95", "47.72"),
            ("0.03", "100.0", "38.08"),
        ]

        # Fill table rows
        rows = page.locator("#diag-test-table-tbody tr")
        for i, (x_val, t_val, u_val) in enumerate(verified_readings):
            inputs = rows.nth(i).locator(".cell-input")
            inputs.nth(0).fill(x_val)
            inputs.nth(1).fill(t_val)
            inputs.nth(2).fill(u_val)
        time.sleep(0.3)

        # Run diagnosis
        page.click("#diag-submit-btn")
        page.wait_for_selector("#diag-result-panel", state="visible", timeout=15000)

        # Verify Diagnose verdict flags reading #3
        traffic_title = page.locator("#diag-traffic-title").inner_text()
        assert "Reading #3 looks faulty" in traffic_title

        # Open Show details and verify required line is present
        page.click("#diag-details-disclosure summary")
        page.wait_for_selector("#diag-details-crosscheck-note", state="visible", timeout=3000)
        details_text = page.locator("#diag-details-crosscheck-note").inner_text().strip()
        assert "Estimate can still pass because it only checks that a smooth heat curve fits; Diagnose compares against your healthy reference." in details_text

        # Verify Diagnose Cross-check banner
        page.wait_for_selector("#diag-crosscheck-banner", state="visible", timeout=5000)
        diag_banner = page.locator("#diag-crosscheck-banner")
        assert "amber" in diag_banner.get_attribute("class")
        diag_banner_text = diag_banner.inner_text()
        expected_msg = "The readings fit a heat curve, but they differ from your healthy reference (reading #3 looks faulty). The estimate may be less reliable. Try Estimate without reading 3."
        assert expected_msg in diag_banner_text

        # Test clicking the action button inside Diagnose banner: "Estimate without reading 3"
        action_btn = page.locator("#diag-crosscheck-banner #crosscheck-remove-fault-btn")
        page.wait_for_selector("#diag-crosscheck-banner #crosscheck-remove-fault-btn", state="visible")
        action_btn.click()
        time.sleep(0.5)

        # Navigated to Estimate: verify reading #3 was removed (table now has 9 rows) and removed sensor note appears
        assert page.locator("#est-table-tbody tr").count() == 9
        assert page.locator("#est-removed-sensor-note").is_visible()
        assert "Reading #3 was removed" in page.locator("#est-removed-sensor-text").inner_text()

        # Run Estimate on the cleaned data
        page.wait_for_selector("#est-submit-btn", state="visible")
        page.click("#est-submit-btn")
        page.wait_for_selector("#est-result-panel", state="visible", timeout=15000)

        # Verify Cross-Check banner is removed from Estimate view completely
        assert page.locator("#est-crosscheck-banner").count() == 0
        assert page.locator("#est-goto-diagnose-btn").is_visible()

        browser.close()

def test_crosscheck_case3_estimate_flagged_diagnose_green(live_server):
    """Case 3: Readings match healthy reference, but setup values do not fit heat model."""
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 1440, "height": 900})

        # 1. Load Diagnose with default bar profile and healthy example readings
        page.goto(f"{live_server}/#diagnose")
        page.select_option("#diag-profile-select", value="00000000-0000-4000-8000-000000000001")
        time.sleep(0.3)
        page.click("#diag-use-example-btn")
        time.sleep(0.3)

        # Run Diagnose -> Healthy (green)
        page.click("#diag-submit-btn")
        page.wait_for_selector("#diag-result-panel", state="visible", timeout=15000)
        assert "Everything looks normal." in page.locator("#diag-traffic-title").inner_text()

        # 2. Go to Estimate, but alter setup values so model fit fails (e.g. Tb=50.0 instead of 20.0)
        page.goto(f"{live_server}/#estimate")
        page.fill("#est-temp-edge", "50.0")
        time.sleep(0.2)

        # Run Estimate
        page.click("#est-submit-btn")
        page.wait_for_selector("#est-result-panel", state="visible", timeout=15000)

        # Estimate traffic banner flags model_invalid
        est_title = page.locator("#est-traffic-title").inner_text()
        assert "your readings do not fit the heat model" in est_title

        # Check Estimate Cross-Check banner is removed
        assert page.locator("#est-crosscheck-banner").count() == 0
        assert page.locator("#est-goto-diagnose-btn").is_visible()
        expected_msg = "The readings match your reference but do not fit the heat model. Check your setup values (length, duration, temperatures)."

        # 3. Check Diagnose page also displays Case 3 banner
        page.goto(f"{live_server}/#diagnose")
        page.wait_for_selector("#diag-crosscheck-banner", state="visible", timeout=5000)
        diag_banner = page.locator("#diag-crosscheck-banner")
        assert "amber" in diag_banner.get_attribute("class")
        assert expected_msg in diag_banner.inner_text()

        browser.close()
