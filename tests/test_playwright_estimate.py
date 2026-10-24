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
        print("resp1 flags:", resp1["flags"])
        banner_class = page.locator("#est-traffic-banner").get_attribute("class")
        print("banner_class:", banner_class)
        assert "green" in banner_class or "amber" in banner_class

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
        assert 0.90e-5 <= alpha2 <= 1.10e-5, f"mode3 alpha {alpha2} not within 10% of 1.0e-5"
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
        assert 0.90e-5 <= alpha3 <= 1.10e-5, f"mode2 alpha {alpha3} not within 10% of 1.0e-5"
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
        assert 0.90e-5 <= alpha4 <= 1.10e-5, f"declared_physics alpha {alpha4} not within 10% of 1.0e-5"
        assert ci4[0] <= 1.0e-5 <= ci4[1], f"declared_physics CI {ci4} does not contain 1.0e-5"


        browser.close()
