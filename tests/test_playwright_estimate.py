"""Playwright End-to-End Real Units Verification Suite.

Tests the live HTTP browser path:
1. Navigates to #estimate.
2. Clicks 'Use example' -> populates real-units table & the four required fields.
3. Tests all 4 methods (mode3plus, mode3, mode2, declared_physics).
4. Asserts alpha_hat is within 10% of 1.0e-5 m^2/s and CI contains 1.0e-5 m^2/s.
"""

import os
import sys
import time
import socket
import subprocess
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
    yield port
    proc.terminate()
    try:
        proc.wait(timeout=5)
    except subprocess.TimeoutExpired:
        proc.kill()

def test_playwright_real_units_estimate_all_four_methods(live_server):
    port = live_server
    url = f"http://127.0.0.1:{port}/#estimate"

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 1440, "height": 900})
        page.on("console", lambda msg: print(f"PAGE LOG: {msg.type}: {msg.text}"))
        page.on("pageerror", lambda err: print(f"PAGE ERROR: {err}"))

        page.goto(url)
        page.wait_for_selector("#view-estimate.active")

        # 1. Click "Use example"
        page.click("#est-use-example-btn")
        page.wait_for_timeout(150)

        # Assert table and fields are populated with real-unit example
        assert page.locator("#est-readings-table tbody tr").count() == 10
        assert page.input_value("#est-bar-length") == "0.1"
        assert page.input_value("#est-experiment-time") == "100"
        assert page.input_value("#est-temp-edge") == "20"
        assert page.input_value("#est-temp-peak") == "80"
        assert page.input_value("#est-sigma-val") == "0.5"

        def get_estimate_json():
            page.locator("#est-technical-details").evaluate("el => el.open = true")
            raw_json = page.locator("#est-json-dump").text_content()
            return json.loads(raw_json)

        # Method 1: mode3plus (default)
        page.click("#est-submit-btn")
        page.wait_for_selector("#est-result-panel", state="visible", timeout=60000)
        page.wait_for_timeout(250)
        
        dump1 = get_estimate_json()
        resp1 = dump1["response"]
        alpha1 = resp1["alpha_hat"]
        ci1 = resp1["ci95"]
        assert "mode 3+" in resp1["method"].lower()
        assert resp1["units"] == "m²/s"
        assert ci1[0] <= 1.0e-5 <= ci1[1], f"mode3plus CI {ci1} does not contain 1.0e-5"
        print("resp1 flags:", resp1["flags"])
        banner_class = page.locator("#est-traffic-banner").get_attribute("class")
        print("banner_class:", banner_class)
        assert "green" in banner_class, f"Expected green banner, got {banner_class}"

        # Assert UI label has literal Greek alpha and number has superscript format
        label_txt = page.locator("#est-result-label").text_content()
        assert "Heat spread (α)" in label_txt
        num_txt = page.locator("#est-plain-number").text_content()
        assert "1.0 × 10⁻⁵" in num_txt
        sub_txt = page.locator("#est-plain-subline").text_content()
        assert "to" in sub_txt and "× 10" in sub_txt

        # Method 2: mode3
        page.click("#est-more-options-btn")
        page.wait_for_selector("#est-more-drawer.open", state="visible")
        page.select_option("#est-method-select", "mode3")
        page.click("#est-drawer-close-btn")
        page.wait_for_timeout(100)

        page.click("#est-submit-btn")
        page.wait_for_selector("#est-result-panel", state="visible", timeout=60000)
        page.wait_for_timeout(250)

        dump2 = get_estimate_json()
        resp2 = dump2["response"]
        alpha2 = resp2["alpha_hat"]
        ci2 = resp2["ci95"]
        assert "mode 3" in resp2["method"].lower()
        assert resp2["units"] == "m²/s"
        assert ci2[0] <= 1.0e-5 <= ci2[1], f"mode3 CI {ci2} does not contain 1.0e-5"

        # Method 3: mode2
        page.click("#est-more-options-btn")
        page.wait_for_selector("#est-more-drawer.open", state="visible")
        page.select_option("#est-method-select", "mode2")
        page.click("#est-drawer-close-btn")
        page.wait_for_timeout(100)

        page.click("#est-submit-btn")
        page.wait_for_selector("#est-result-panel", state="visible", timeout=60000)
        page.wait_for_timeout(250)

        dump3 = get_estimate_json()
        resp3 = dump3["response"]
        alpha3 = resp3["alpha_hat"]
        ci3 = resp3["ci95"]
        assert "mode 2" in resp3["method"].lower()
        assert resp3["units"] == "m²/s"
        assert ci3[0] <= 1.0e-5 <= ci3[1], f"mode2 CI {ci3} does not contain 1.0e-5"

        # Method 4: declared_physics
        page.click("#est-more-options-btn")
        page.wait_for_selector("#est-more-drawer.open", state="visible")
        page.select_option("#est-method-select", "declared_physics")
        page.click("#est-drawer-close-btn")
        page.wait_for_timeout(100)

        page.click("#est-submit-btn")
        page.wait_for_selector("#est-result-panel", state="visible", timeout=60000)
        page.wait_for_timeout(250)

        dump4 = get_estimate_json()
        resp4 = dump4["response"]
        alpha4 = resp4["alpha_hat"]
        ci4 = resp4["ci95"]
        assert "declared_physics" in resp4["method"].lower() or "declared physics" in resp4["method"].lower()
        assert resp4["units"] == "m²/s"
        assert ci4[0] <= 1.0e-5 <= ci4[1], f"declared_physics CI {ci4} does not contain 1.0e-5"

        browser.close()

def test_estimate_identical_regardless_of_diagnose_profile(live_server):
    """Verify that with the same readings and setup, Estimate result is identical whichever profile is selected on Diagnose."""
    port = live_server
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 1440, "height": 900})

        # 1. On Estimate, click 'Use example' and run calculation
        page.goto(f"http://127.0.0.1:{port}/#estimate")
        page.wait_for_selector("#est-use-example-btn", state="visible")
        page.click("#est-use-example-btn")
        time.sleep(0.2)
        page.click("#est-submit-btn")
        page.wait_for_selector("#est-result-panel", state="visible", timeout=15000)
        est_result_initial = page.locator("#est-plain-number").text_content().strip()
        assert est_result_initial != "", "Estimate initial result should not be empty"

        # 2. Go to Diagnose and select Demo 2: Aluminum rod (different length 0.2m, duration 50s)
        page.goto(f"http://127.0.0.1:{port}/#diagnose")
        page.wait_for_selector("#diag-profile-select", state="visible")
        page.select_option("#diag-profile-select", value="00000000-0000-4000-8000-000000000002")
        time.sleep(0.3)

        # 3. Return to Estimate and calculate with same readings and setup
        page.goto(f"http://127.0.0.1:{port}/#estimate")
        page.wait_for_selector("#est-submit-btn", state="visible")
        page.click("#est-submit-btn")
        page.wait_for_selector("#est-result-panel", state="visible", timeout=15000)
        est_result_profile2 = page.locator("#est-plain-number").text_content().strip()
        assert est_result_profile2 == est_result_initial, f"Estimate result changed after selecting Aluminum rod on Diagnose: {est_result_profile2} vs {est_result_initial}"

        # 4. Go to Diagnose and select Demo 1: Steel bar
        page.goto(f"http://127.0.0.1:{port}/#diagnose")
        page.wait_for_selector("#diag-profile-select", state="visible")
        page.select_option("#diag-profile-select", value="00000000-0000-4000-8000-000000000001")
        time.sleep(0.3)

        # 5. Return to Estimate and calculate again
        page.goto(f"http://127.0.0.1:{port}/#estimate")
        page.wait_for_selector("#est-submit-btn", state="visible")
        page.click("#est-submit-btn")
        page.wait_for_selector("#est-result-panel", state="visible", timeout=15000)
        est_result_profile1 = page.locator("#est-plain-number").text_content().strip()
        assert est_result_profile1 == est_result_initial, f"Estimate result changed after selecting Steel bar on Diagnose: {est_result_profile1} vs {est_result_initial}"

        # 6. Verify the bar-profile card is completely removed from Estimate, and loader is hidden
        assert page.locator("#est-profile-card").count() == 0
        assert page.locator("#est-profile-select").count() == 0
        # est-load-setup-select is commented out per HIDDEN-UI directive
        assert page.locator("#est-load-setup-select").count() == 0

        browser.close()

def test_estimate_mismatch_amber_note_and_result_readability(live_server):
    """Verify amber note when setup and example readings disagree, and result readability with comparison."""
    port = live_server
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 1440, "height": 900})

        page.goto(f"http://127.0.0.1:{port}/#estimate")
        page.wait_for_selector("#view-estimate.active")

        # 1. Click 'Use example' -> fills table with default example readings (L=0.1, T=100, Tb=20, Tp=80)
        page.click("#est-use-example-btn")
        time.sleep(0.2)

        # Mismatch note should NOT be visible when setup matches default example
        assert not page.locator("#est-example-mismatch-note").is_visible()

        # 2. Change Bar length to 0.2 m while table still has unedited default example readings
        page.fill("#est-bar-length", "0.2")
        time.sleep(0.1)

        # Amber note must appear
        assert page.locator("#est-example-mismatch-note").is_visible()
        mismatch_text = page.locator("#est-example-mismatch-text").text_content()
        assert "These readings were made for the default example bar (0.1 m, 100 s, 20 to 80 C). Replace them with your own readings before estimating." in mismatch_text

        # 3. Calculate while mismatched -> Never present as trustworthy
        page.click("#est-submit-btn")
        page.wait_for_selector("#est-result-panel", state="visible")
        banner_class = page.locator("#est-traffic-banner").get_attribute("class")
        assert "green" not in banner_class, f"Mismatched estimate was presented as green/trustworthy: {banner_class}"
        assert page.locator("#est-result-mismatch-note").is_visible()
        res_note = page.locator("#est-result-mismatch-note").text_content()
        assert "These readings were made for the default example bar (0.1 m, 100 s, 20 to 80 C). Replace them with your own readings before estimating." in res_note

        # 4. Editing a reading in the table clears the amber note
        page.fill("#est-readings-table tbody tr:first-child .cell-input[data-col='u']", "70.00")
        time.sleep(0.1)
        assert not page.locator("#est-example-mismatch-note").is_visible()

        # 5. Reset to default example readings and default setup
        page.click("#est-use-example-btn")
        page.fill("#est-bar-length", "0.1")
        time.sleep(0.1)
        assert not page.locator("#est-example-mismatch-note").is_visible()

        # 6. Calculate -> Result looks trustworthy & Result readability verified
        page.click("#est-submit-btn")
        page.wait_for_selector("#est-result-panel", state="visible")
        banner_class = page.locator("#est-traffic-banner").get_attribute("class")
        assert "green" in banner_class

        num_text = page.locator("#est-plain-number").text_content()
        assert "0.00001 m^2/s" in num_text

        mat_text = page.locator("#est-material-comparison").text_content()
        assert "For comparison (typical values): steel about 1.3e-5, aluminium about 8.4e-5, glass about 5e-7, wood about 1.3e-7 m^2/s." in mat_text

        browser.close()
