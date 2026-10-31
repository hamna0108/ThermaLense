import os
import sys
import time
import socket
import subprocess
import threading
import json
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

    def drain_pipe():
        try:
            for line in iter(proc.stdout.readline, ''):
                if not line:
                    break
        except Exception:
            pass

    drain_thread = threading.Thread(target=drain_pipe, daemon=True)
    drain_thread.start()

    assert wait_for_port(port, timeout=60), "Server failed to start in 60s"
    yield f"http://127.0.0.1:{port}"

    proc.terminate()
    try:
        proc.wait(timeout=3)
    except subprocess.TimeoutExpired:
        proc.kill()

def test_playwright_diagnose_real_units_and_baseline_conversion(live_server):
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()

        console_errors = []
        page.on("console", lambda msg: console_errors.append(msg.text) if msg.type == "error" else None)

        # 1. Test two-way synchronization of test fields between Estimate and Diagnose
        page.goto(f"{live_server}/#estimate")
        page.wait_for_selector("#view-estimate.active")
        page.fill("#est-bar-length", "0.15")

        page.goto(f"{live_server}/#diagnose")
        page.wait_for_selector("#view-diagnose.active")
        diag_len = page.input_value("#diag-bar-length")
        assert diag_len == "0.15", f"Expected synced bar length 0.15, got {diag_len}"

        page.fill("#diag-experiment-time", "120")
        page.goto(f"{live_server}/#estimate")
        page.wait_for_selector("#view-estimate.active")
        est_dur = page.input_value("#est-experiment-time")
        assert est_dur == "120", f"Expected synced duration 120, got {est_dur}"

        # 2. Test "Use example" populates real units & Prove baseline conversion
        page.goto(f"{live_server}/#diagnose")
        page.wait_for_selector("#view-diagnose.active")

        # Empty state check: result card hidden
        assert not page.locator("#diagnose-results-card").is_visible()

        # Click "Use example"
        page.click("#diag-use-example-btn")

        # Verify counters
        base_badge = page.locator("#diag-baseline-count").text_content()
        assert "20 readings ✓" in base_badge
        test_badge = page.locator("#diag-test-count").text_content()
        assert "10 readings ✓" in test_badge

        # Intercept diagnose request and click "Check my test"
        with page.expect_response(lambda r: "/v1/diagnose" in r.url and r.request.method == "POST") as resp_info:
            page.click("#diag-submit-btn")
        
        resp = resp_info.value.json()
        req = resp_info.value.request.post_data_json
        page.wait_for_selector("#diag-result-panel", state="visible")

        # Verify outgoing payload is in physical units
        assert req["bar_length_m"] == 0.1
        assert req["test_duration_s"] == 100
        assert req["boundary_temperature"] == 20
        assert req["initial_peak_temperature"] == 80
        assert len(req["baseline"]["y"]) == 20
        assert len(req["readings"]["y"]) == 10
        # Temperatures are physical > 20 °C
        assert min(req["baseline"]["y"]) > 20.0
        assert max(req["baseline"]["y"]) <= 80.0

        # PROOF THAT BASELINE IS CONVERTED:
        # Check normalization object returned by backend
        assert resp["normalization"]["bar_length_m"] == 0.1
        assert resp["normalization"]["test_duration_s"] == 100
        assert resp["normalization"]["boundary_temperature"] == 20
        assert resp["normalization"]["initial_peak_temperature"] == 80
        assert abs(resp["normalization"]["scale_factor"] - 1e-4) < 1e-9

        # Baseline alpha in real units should be ~ 1.0e-5 m^2/s (0.000010)
        # If baseline had NOT been converted, alpha_baseline would be ~ 0.10!
        alpha_base = resp["evidence_stats"]["alpha_baseline"]
        assert 0.8e-5 <= alpha_base <= 1.2e-5, f"Baseline alpha {alpha_base} is not in real m²/s units (expected ~1.0e-5)"
        assert resp["assigned_class"] == "H"
        assert resp["units"] == "m²/s"

        # Verify UI Result Banner for Class H
        banner_cls = page.locator("#diag-traffic-banner").get_attribute("class")
        assert "green" in banner_cls
        assert "Everything looks normal." in page.locator("#diag-traffic-title").text_content()

        # Verify heat spread comparison line
        assert page.locator("#diag-heat-spread-line").is_visible()
        heat_line_h = page.locator("#diag-heat-spread-line").text_content()
        assert "Normal heat spread (reference):" in heat_line_h
        assert "This test:" in heat_line_h
        assert ("m²/s" in heat_line_h) or ("m^2/s" in heat_line_h)
        assert "(within normal range)" in heat_line_h

        # Verify Show details concept note
        assert page.locator("#diag-details-ref-concept-note").text_content() == "The reference defines what normal looks like. Estimate finds the heat spread from this test alone; Diagnose compares the test with your reference."

        # Verify Honesty Note is visible and links to evidence
        assert page.locator("#diag-honesty-note").is_visible()
        honesty_txt = page.locator("#diag-honesty-note").text_content()
        assert "Typical accuracy: normal tests flagged wrongly about 6%" in honesty_txt
        assert page.locator("#diag-honesty-evidence-link").get_attribute("href") == "#evidence"

        # 3. Test Demo Scenarios (Class A, F_stuck, C, and Refusal)
        # Class A: Anomalous Heat Spread
        page.select_option("#diag-scenario-select", "A")
        page.click("#diag-submit-btn")
        page.wait_for_selector("#diag-result-panel", state="visible")
        banner_cls = page.locator("#diag-traffic-banner").get_attribute("class")
        assert "amber" in banner_cls
        assert "The material behaves differently from your reference run." in page.locator("#diag-traffic-title").text_content()
        heat_line_a = page.locator("#diag-heat-spread-line").text_content()
        assert "Normal heat spread (reference):" in heat_line_a
        assert "This test:" in heat_line_a
        assert ("m²/s" in heat_line_a) or ("m^2/s" in heat_line_a)
        assert "(different from normal)" in heat_line_a

        # Class F: Sensor Fault (Sensor 3 stuck)
        page.select_option("#diag-scenario-select", "F_stuck")
        page.click("#diag-submit-btn")
        page.wait_for_selector("#diag-result-panel", state="visible")
        f_title = page.locator("#diag-traffic-title").text_content()
        assert "Reading #3 looks faulty (position 0.03 m, time 4.6 s). Possible causes: stuck, offset or wrong scale." in f_title
        assert page.locator("#diag-goto-estimate-without-fault-btn").text_content() == "Estimate without reading 3"
        assert page.locator("#diag-detector-scope-note").text_content() == "The detector is built for one or two isolated bad readings, not a sensor that is wrong for the whole test."

        # Class C: Change-Point (jump around 35 s)
        page.select_option("#diag-scenario-select", "C")
        page.click("#diag-submit-btn")
        page.wait_for_selector("#diag-result-panel", state="visible")
        c_title = page.locator("#diag-traffic-title").text_content()
        assert "The behaviour changed during the test, around 35 s." in c_title

        # Refusal: baseline k=10 < 20
        page.select_option("#diag-scenario-select", "refusal_baseline")
        page.click("#diag-submit-btn")
        page.wait_for_selector("#diag-traffic-banner.red", state="visible")
        ref_title = page.locator("#diag-traffic-title").text_content()
        assert "A reference run needs at least 20 readings to establish normal behavior. You entered 10 readings." in ref_title

        browser.close()

def test_playwright_diagnose_saved_reference(live_server):
    """Playwright E2E: save a reference, reload page, load saved reference, run Check my test with zero console errors."""
    url = f"{live_server}/#diagnose"

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context()
        page = context.new_page()

        console_errors = []
        page.on("console", lambda msg: console_errors.append(msg.text) if msg.type == "error" else None)

        page.goto(url)
        page.wait_for_selector("#view-diagnose", state="visible")

        # Use example to populate baseline and test tables
        page.click("#diag-use-example-btn")
        page.wait_for_timeout(300)

        # Click "Save as bar profile"
        save_btn = page.locator("#diag-save-profile-btn")
        save_btn.click()
        page.wait_for_selector("#diag-save-profile-form", state="visible")

        # Fill name
        ref_name = "Steel rod, lab A"
        page.fill("#diag-save-profile-name-input", ref_name)
        page.click("#diag-confirm-save-profile-btn")
        page.wait_for_timeout(400)

        # Verify selector now has the option
        sel_text = page.locator("#diag-profile-select").inner_text()
        assert ref_name in sel_text

        # Reload the page
        page.reload()
        page.wait_for_selector("#view-diagnose", state="visible")

        # Select saved bar profile
        options = page.locator("#diag-profile-select option").all()
        target_val = None
        for opt in options:
            if ref_name in opt.inner_text():
                target_val = opt.get_attribute("value")
                break
        assert target_val is not None
        page.select_option("#diag-profile-select", target_val)
        page.wait_for_timeout(400)

        # Verify metadata is displayed
        meta_text = page.locator("#diag-profile-meta-bar").text_content()
        assert ref_name in meta_text
        assert "20 readings" in meta_text

        # Verify reference table has 20 readings loaded
        base_rows = page.locator("#diag-base-table-tbody tr").count()
        assert base_rows == 20

        # Verify test setup fields are populated
        assert page.input_value("#diag-bar-length") == "0.1"
        assert page.input_value("#diag-experiment-time") == "100"

        # Populate test table with at least 3 test readings
        test_rows = page.locator("#diag-test-table-tbody tr").count()
        if test_rows < 3:
            page.click("#diag-test-add-row-btn")

        page.fill("#diag-test-pos-1", "0.05")
        page.fill("#diag-test-time-1", "10.0")
        page.fill("#diag-test-temp-1", "75.0")
        page.fill("#diag-test-pos-2", "0.05")
        page.fill("#diag-test-time-2", "30.0")
        page.fill("#diag-test-temp-2", "60.0")
        page.fill("#diag-test-pos-3", "0.05")
        page.fill("#diag-test-time-3", "80.0")
        page.fill("#diag-test-temp-3", "45.0")

        # Click Check my test
        page.click("#diag-submit-btn")
        page.wait_for_selector("#diag-result-panel", state="visible")

        # Assert results card appears
        assert page.is_visible("#diag-traffic-banner")

        # Switch to Estimate tab and confirm the setup is filled
        page.click("#nav-estimate")
        page.wait_for_selector("#view-estimate.active", state="visible")
        assert page.input_value("#est-bar-length") == "0.1"
        assert page.input_value("#est-experiment-time") == "100"
        assert page.input_value("#est-temp-edge") == "20"
        assert page.input_value("#est-temp-peak") == "80"
        assert page.input_value("#est-sigma-val") == "0.5"

        # Switch back to Diagnose tab
        page.click("#nav-diagnose")
        page.wait_for_selector("#view-diagnose.active", state="visible")

        # Test Rename
        page.click("#diag-profile-rename-btn")
        page.wait_for_selector("#diag-profile-rename-form", state="visible")
        page.fill("#diag-profile-rename-input", "Steel rod, lab B")
        page.click("#diag-profile-confirm-rename-btn")
        page.wait_for_timeout(300)
        assert "Steel rod, lab B" in page.locator("#diag-profile-meta-bar").text_content()

        # Test Delete
        page.on("dialog", lambda dialog: dialog.accept())
        page.click("#diag-profile-delete-btn")
        page.wait_for_timeout(300)
        assert "Steel rod, lab B" not in page.locator("#diag-profile-select").inner_text()

        # Assert zero console errors
        assert len(console_errors) == 0

        browser.close()
