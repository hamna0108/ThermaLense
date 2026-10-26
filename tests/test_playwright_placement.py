"""Playwright End-to-End Test Suite for Sensor Placement Workbench.

Verifies:
1. Middle default position (e.g. 0.05 m for 0.1 m bar length).
2. Customer-friendly input names, hint text, and plain-words "How this works" explanation.
3. Position validation: rejection at x <= 0 or x >= L with plain message; warning if within 10% of an end.
4. Schedule calculation returning Early readings and Focused readings tables in seconds, plus expected cooling curve chart.
5. "Use these times in Estimate" button fills scheduled times and shared setup into Estimate tab.
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
    """Start uvicorn in a background process with stdout draining."""
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

    assert wait_for_port(port, timeout=60), "Server failed to start in 60s"
    yield f"http://127.0.0.1:{port}"

    proc.terminate()
    try:
        proc.wait(timeout=3)
    except subprocess.TimeoutExpired:
        proc.kill()


def test_placement_middle_default_and_handoff_to_estimate(live_server):
    """Test that sensor position defaults to middle of bar, computes schedule, and transfers to Estimate."""
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        page.goto(f"{live_server}/#placement")
        page.wait_for_load_state("networkidle")

        # 1. Verify input names and middle default
        lbl_n = page.locator("#place-lbl-n")
        assert "how many readings can you take?" in lbl_n.inner_text().lower()

        lbl_sigma = page.locator("#place-lbl-sigma")
        assert "thermometer accuracy" in lbl_sigma.inner_text().lower()

        lbl_x = page.locator("#place-lbl-sensor-x")
        assert "sensor position (m from the left end)" in lbl_x.inner_text().lower()


        hint_x = page.locator("#place-sensor-x-hint")
        assert "The middle of the bar gives the strongest signal" in hint_x.inner_text()

        bar_len = page.locator("#place-bar-length").input_value()
        sensor_x = page.locator("#place-sensor-x").input_value()
        assert float(bar_len) == 0.1
        # Middle default for 0.1 m bar is 0.05 m
        assert float(sensor_x) == 0.05

        # 2. Check defaults
        assert page.locator("#place-n").input_value() == "10"
        assert page.locator("#place-sigma").input_value() == "0.5"
        assert page.locator("#place-tmin").input_value() == "1.0"
        assert page.locator("#place-tmax").input_value() == "100.0"

        # 3. Compute sampling schedule
        page.locator("#place-submit-btn").click()
        page.locator("#place-result-panel").wait_for(state="visible", timeout=10000)

        # 4. Check "How this works" explanation
        how_it_works = page.locator(".place-how-it-works")
        assert "How this works:" in how_it_works.inner_text()
        assert "early readings" in how_it_works.inner_text()
        assert "focused readings" in how_it_works.inner_text()

        # 5. Check early readings and focused readings tables
        t1_rows = page.locator("#place-t1-tbody tr")
        t2_rows = page.locator("#place-t2-tbody tr")
        assert t1_rows.count() == 5  # N=10 split equally 5 and 5
        assert t2_rows.count() == 5

        # Verify units are formatted in seconds
        t1_first = t1_rows.nth(0).locator("td").nth(1).inner_text()
        assert t1_first.endswith(" s")
        t2_first = t2_rows.nth(0).locator("td").nth(1).inner_text()
        assert t2_first.endswith(" s")

        # 6. Check cooling curve chart SVG
        svg_content = page.locator("#place-chart-svg").inner_html()
        assert "<path" in svg_content
        assert "<circle" in svg_content
        assert "Early reading" in svg_content
        assert "Focused reading" in svg_content

        # 7. Check "Use these times in Estimate" button
        use_times_btn = page.locator("#place-use-times-btn")
        assert use_times_btn.is_visible()
        use_times_btn.click()

        # Should navigate to Estimate tab
        page.wait_for_timeout(500)
        assert "#estimate" in page.url

        # Shared setup should be filled in Estimate
        assert page.locator("#est-bar-length").input_value() == "0.1"
        assert page.locator("#est-experiment-time").input_value() == "100"
        assert page.locator("#est-temp-edge").input_value() == "20"
        assert page.locator("#est-temp-peak").input_value() == "80"
        assert page.locator("#est-sigma-val").input_value() == "0.5"

        # Readings table should have 10 rows filled with sensor_x=0.05 and times in seconds
        est_rows = page.locator("#est-table-tbody tr")
        assert est_rows.count() == 10
        for i in range(10):
            row_x = est_rows.nth(i).locator('input[placeholder="e.g. 0.05"]').input_value()
            row_t = est_rows.nth(i).locator('input[placeholder="e.g. 10.0"]').input_value()
            assert row_x == "0.05"
            assert float(row_t) > 0

        browser.close()


def test_placement_position_validation_and_rejection(live_server):
    """Test rejection at x <= 0 or x >= L with plain message, and warning within 10% of an end."""
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        page.goto(f"{live_server}/#placement")
        page.wait_for_load_state("networkidle")

        sensor_x_input = page.locator("#place-sensor-x")
        msg_el = page.locator("#place-sensor-x-msg")
        submit_btn = page.locator("#place-submit-btn")

        # 1. Reject position at 0
        sensor_x_input.fill("0")
        page.wait_for_timeout(100)
        assert "Sensor position cannot be at or outside the ends of the bar" in msg_el.inner_text()
        assert submit_btn.is_disabled()

        # 2. Reject position at bar length (0.1)
        sensor_x_input.fill("0.1")
        page.wait_for_timeout(100)
        assert "Sensor position cannot be at or outside the ends of the bar" in msg_el.inner_text()
        assert submit_btn.is_disabled()

        # 3. Reject negative position
        sensor_x_input.fill("-0.02")
        page.wait_for_timeout(100)
        assert "Sensor position cannot be at or outside the ends of the bar" in msg_el.inner_text()
        assert submit_btn.is_disabled()

        # 4. Warn if position is within 10% of left end (e.g. 0.005 < 0.01)
        sensor_x_input.fill("0.005")
        page.wait_for_timeout(100)
        assert "within 10% of an end" in msg_el.inner_text()
        assert not submit_btn.is_disabled()

        # 5. Warn if position is within 10% of right end (e.g. 0.095 > 0.09)
        sensor_x_input.fill("0.095")
        page.wait_for_timeout(100)
        assert "within 10% of an end" in msg_el.inner_text()
        assert not submit_btn.is_disabled()

        # 6. Valid middle position clears warning and error
        sensor_x_input.fill("0.05")
        page.wait_for_timeout(100)
        assert msg_el.inner_text() == ""
        browser.close()


def test_placement_material_guess_and_refine_flow(live_server):
    """Test material guess field, helper text, and refinement workflow from Estimate fit."""
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()

        # 1. Open placement page and check material guess input + hint
        page.goto(f"{live_server}/#placement")
        page.wait_for_load_state("networkidle")

        mat_input = page.locator("#place-material-guess")
        assert mat_input.is_visible()
        assert mat_input.input_value() == "1e-5"

        hint = page.locator("#place-material-guess-hint")
        assert "Focused times assume a typical heat spread" in hint.inner_text()
        assert "adjust the material guess if you know it" in hint.inner_text()

        refine_box = page.locator("#place-refine-box")
        assert refine_box.is_visible()
        refine_btn = page.locator("#place-refine-btn")
        refine_msg = page.locator("#place-refine-msg")

        # 2. Clicking refine before running Estimate displays informational notice
        refine_btn.click()
        page.wait_for_timeout(200)
        assert "No estimate found yet" in refine_msg.inner_text()

        # 3. Compute initial placement with default 1e-5
        page.locator("#place-submit-btn").click()
        page.locator("#place-result-panel").wait_for(state="visible", timeout=10000)
        t2_first_text_default = page.locator("#place-t2-tbody tr td").nth(1).inner_text()

        # 4. Navigate to Estimate, load default example readings, and run Estimate
        page.goto(f"{live_server}/#estimate")
        page.wait_for_load_state("networkidle")
        page.locator("#est-use-example-btn").click()
        page.wait_for_timeout(300)
        page.locator("#est-submit-btn").click()
        page.locator("#estimate-results-card").wait_for(state="visible", timeout=10000)

        # 5. Return to Placement and refine using the estimate fit
        page.goto(f"{live_server}/#placement")
        page.wait_for_load_state("networkidle")
        refine_btn.click()
        page.wait_for_timeout(500)

        # Confirm material guess was refined and schedule was re-computed
        assert "✓ Refined using Estimate" in refine_msg.inner_text()
        refined_val = float(mat_input.input_value())
        assert refined_val > 0
        page.locator("#place-result-panel").wait_for(state="visible", timeout=10000)

        browser.close()

