"""Playwright Test Suite for Shared-Readings Sync Across Estimate and Diagnose.

Verifies:
(a) changing the seed in Estimate (42 -> 10 -> 7) updates both Estimate and Diagnose test tables identically each time;
(b) 'Use example' populates both tables identically;
(c) CSV upload populates both tables identically;
(d) Place Sensors 'Use these times' populates both tables identically;
(e) 'Clear my data' empties both tables (3 blank rows).
All rows are compared exactly between Estimate and Diagnose test tables.
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


def extract_table_rows(page, tbody_selector):
    """Extract rows and cell input values from a table body."""
    rows = page.locator(f"{tbody_selector} tr")
    data = []
    for i in range(rows.count()):
        inputs = rows.nth(i).locator(".cell-input")
        row_vals = [inputs.nth(j).input_value().strip() for j in range(inputs.count())]
        data.append(row_vals)
    return data


def test_seed_change_sync_estimate_diagnose(live_server):
    """Test that changing seed (42 -> 10 -> 7) updates Estimate and Diagnose test tables identically."""
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        page.goto(f"{live_server}/#estimate")
        page.wait_for_load_state("networkidle")

        # 1. Seed 42: both tables match
        est_rows_42 = extract_table_rows(page, "#est-table-tbody")
        diag_rows_42 = extract_table_rows(page, "#diag-test-table-tbody")
        assert est_rows_42 == diag_rows_42
        assert len(est_rows_42) >= 3

        # 2. Change seed to 10
        seed_input = page.locator("#est-seed")
        seed_input.fill("10")
        page.wait_for_timeout(200)

        est_rows_10 = extract_table_rows(page, "#est-table-tbody")
        diag_rows_10 = extract_table_rows(page, "#diag-test-table-tbody")
        assert est_rows_10 == diag_rows_10, f"Mismatch on seed 10:\nEst: {est_rows_10}\nDiag: {diag_rows_10}"
        assert est_rows_10 != est_rows_42, "Seed 10 should generate different values than seed 42"

        # 3. Change seed to 7
        seed_input.fill("7")
        page.wait_for_timeout(200)

        est_rows_7 = extract_table_rows(page, "#est-table-tbody")
        diag_rows_7 = extract_table_rows(page, "#diag-test-table-tbody")
        assert est_rows_7 == diag_rows_7, f"Mismatch on seed 7:\nEst: {est_rows_7}\nDiag: {diag_rows_7}"
        assert est_rows_7 != est_rows_10, "Seed 7 should generate different values than seed 10"

        browser.close()


def test_use_example_sync(live_server):
    """Test that 'Use example' populates both Estimate and Diagnose test tables identically."""
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        page.goto(f"{live_server}/#estimate")
        page.wait_for_load_state("networkidle")

        page.locator("#est-use-example-btn").click()
        page.wait_for_timeout(200)

        est_rows = extract_table_rows(page, "#est-table-tbody")
        diag_rows = extract_table_rows(page, "#diag-test-table-tbody")
        assert est_rows == diag_rows, f"Mismatch on Use example:\nEst: {est_rows}\nDiag: {diag_rows}"
        assert len(est_rows) == 10

        browser.close()


def test_csv_upload_sync(live_server, tmp_path):
    """Test that CSV upload in Estimate populates both tables identically."""
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        page.goto(f"{live_server}/#estimate")
        page.wait_for_load_state("networkidle")

        # Create temporary CSV file
        csv_path = tmp_path / "test_readings.csv"
        csv_content = "position_m,time_s,temp_c\n0.02, 5.0, 45.2\n0.04, 15.0, 32.1\n0.06, 25.0, 24.5\n0.08, 35.0, 21.0\n"
        csv_path.write_text(csv_content, encoding="utf-8")

        page.locator("#est-csv-upload").set_input_files(str(csv_path))
        page.wait_for_timeout(200)

        est_rows = extract_table_rows(page, "#est-table-tbody")
        diag_rows = extract_table_rows(page, "#diag-test-table-tbody")
        assert est_rows == diag_rows, f"Mismatch on CSV upload:\nEst: {est_rows}\nDiag: {diag_rows}"
        assert len(est_rows) == 4
        assert est_rows[0] == ["0.02", "5.0", "45.2"]
        assert est_rows[3] == ["0.08", "35.0", "21.0"]

        browser.close()


def test_place_sensors_times_sync(live_server):
    """Test that Place Sensors 'Use these times' populates both tables identically."""
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        page.goto(f"{live_server}/#placement")
        page.wait_for_load_state("networkidle")

        page.locator("#place-submit-btn").click()
        page.locator("#place-result-panel").wait_for(state="visible", timeout=10000)

        page.locator("#place-use-times-btn").click()
        page.wait_for_timeout(500)
        assert "#estimate" in page.url

        est_rows = extract_table_rows(page, "#est-table-tbody")
        diag_rows = extract_table_rows(page, "#diag-test-table-tbody")
        assert est_rows == diag_rows, f"Mismatch on Place Sensors times:\nEst: {est_rows}\nDiag: {diag_rows}"
        assert len(est_rows) == 10
        for r in est_rows:
            assert r[0] == "0.05"
            assert float(r[1]) > 0
            assert r[2] == ""

        browser.close()


def test_clear_my_data_sync(live_server):
    """Test that 'Clear my data' empties both Estimate and Diagnose test tables."""
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        page.goto(f"{live_server}/#estimate")
        page.wait_for_load_state("networkidle")

        # First load example data to ensure non-empty
        page.locator("#est-use-example-btn").click()
        page.wait_for_timeout(100)

        # Now clear data
        page.locator("#est-clear-data-btn").click()
        page.wait_for_timeout(200)

        est_rows = extract_table_rows(page, "#est-table-tbody")
        diag_rows = extract_table_rows(page, "#diag-test-table-tbody")
        assert est_rows == diag_rows, f"Mismatch on Clear data:\nEst: {est_rows}\nDiag: {diag_rows}"
        assert est_rows == [["", "", ""], ["", "", ""], ["", "", ""]]

        browser.close()
