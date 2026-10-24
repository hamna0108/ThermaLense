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

    assert wait_for_port(port, 30), "Server failed to start in 30s"
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

        # Intercept diagnose request
        diagnose_responses = []
        diagnose_requests = []

        def handle_response(response):
            if "/v1/diagnose" in response.url and response.request.method == "POST":
                diagnose_responses.append(response.json())
                try:
                    diagnose_requests.append(response.request.post_data_json)
                except Exception:
                    pass

        page.on("response", handle_response)

        # Click "Check my test"
        page.click("#diag-submit-btn")
        page.wait_for_selector("#diag-result-panel", state="visible")

        assert len(diagnose_responses) > 0, "No /v1/diagnose response intercepted"
        resp = diagnose_responses[0]
        req = diagnose_requests[0]

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

        # Class F: Sensor Fault (Sensor 3 stuck)
        page.select_option("#diag-scenario-select", "F_stuck")
        page.click("#diag-submit-btn")
        page.wait_for_selector("#diag-result-panel", state="visible")
        f_title = page.locator("#diag-traffic-title").text_content()
        assert "One sensor looks faulty: Sensor 3 (reads stuck / offset / wrong scale)." in f_title

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
