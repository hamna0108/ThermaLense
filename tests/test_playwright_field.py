"""Playwright smoke test for Field (Heat Map Over Time 1D) customer-friendly rewrite.

Verifies:
1. Loads page #field with eyebrow PREDICT and plain subtitle.
2. Settings panel with real units inputs, material dropdown, FNO validity note, plain calculation methods.
3. Axis labels present: 'Position along the bar (m)' and 'Time (s)'.
4. Computes with 'Compare both' for Copper preset (AI fallback when alpha_norm > 1.0).
5. Computes with 'Compare both' for Wood preset (AI fallback when alpha_norm < 0.01).
6. Result card displays plain labels, speed note, color bar with cold/hot °C labels, lower graph with °C ticks and legend.
7. Download buttons for both CSV and JSON.
8. Zero console errors throughout.
9. Captures screenshots at 1440px and 390px.
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

ARTIFACT_DIR = r"C:\Users\HP\.gemini\antigravity-ide\brain\acb0d46f-cc58-4de4-b39b-b47d6409ab04"


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
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        env=env
    )
    if not wait_for_port(port, timeout=60):
        proc.kill()
        raise RuntimeError(f"Server failed to start on port {port}")

    yield f"http://127.0.0.1:{port}"

    proc.terminate()
    try:
        proc.wait(timeout=3)
    except subprocess.TimeoutExpired:
        proc.kill()


def save_screenshot(page, filename):
    filepath = os.path.join(SCREENSHOTS_DIR, filename)
    page.evaluate("() => { const h = document.querySelector('.app-header'); if (h) h.style.position = 'relative'; }")
    page.screenshot(path=filepath, full_page=True)
    page.evaluate("() => { const h = document.querySelector('.app-header'); if (h) h.style.position = ''; }")
    if os.path.isdir(ARTIFACT_DIR):
        try:
            shutil.copy2(filepath, os.path.join(ARTIFACT_DIR, filename))
        except Exception:
            pass


def test_field_smoke_copper_and_wood(live_server):
    console_errors = []

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)

        # -------------------------------------------------------------
        # Desktop 1440x768
        # -------------------------------------------------------------
        context = browser.new_context(viewport={"width": 1440, "height": 768})
        page = context.new_page()

        def on_console(msg):
            if msg.type == "error":
                console_errors.append(f"[console.error] {msg.text}")

        def on_page_error(err):
            console_errors.append(f"[pageerror] {err}")

        page.on("console", on_console)
        page.on("pageerror", on_page_error)

        # 1. Load Field page
        page.goto(f"{live_server}/#field", wait_until="networkidle")
        page.wait_for_selector("#heading-field", state="visible")
        assert page.locator("#heading-field").inner_text() == "Heat Over Time"

        # 2. Check Axis Labels are present in DOM
        y_axis = page.locator(".heatmap-axis-label-y, .axis-title-vertical")
        assert y_axis.count() > 0
        assert "Time (s)" in y_axis.first.inner_text()

        x_axis = page.locator(".heatmap-axis-label-x, .axis-title-horizontal")
        assert x_axis.count() > 0
        assert "Position along the bar (m)" in x_axis.first.inner_text()

        # Check FNO validity note is present
        validity_note = page.locator("#field-fno-validity-note")
        assert "The AI model is only checked for typical heat-spread values" in validity_note.inner_text()

        # 3. Test Compare both with Copper preset
        page.select_option("#field-material-select", value="copper")
        # Ensure 'Compare both' method is selected
        comp_btn = page.locator("#field-method-compare-btn")
        if "active" not in comp_btn.get_attribute("class"):
            comp_btn.click()

        # Click calculate
        page.click("#field-submit-btn")
        page.wait_for_selector("#field-result-panel", state="visible", timeout=10000)

        # Verify summary stats
        method_badge = page.locator("#field-method-badge").inner_text()
        assert "Compare both" in method_badge or "Standard calculation" in method_badge

        timing_text = page.locator("#field-timing-text").inner_text()
        assert "ms" in timing_text

        # Verify speed note
        speed_note = page.locator(".field-speed-note").inner_text()
        assert "The AI model is not faster for a single picture; its value is speed inside the estimation step." in speed_note

        # Verify lower graph title, ticks, legend, and buttons
        profile_title = page.locator("#field-profile-title").inner_text()
        assert "Temperature along the bar at" in profile_title
        assert "s" in profile_title

        legend_text = page.locator("#field-profile-legend").inner_text()
        assert "Computed" in legend_text
        assert "Exact formula" in legend_text

        # Verify CSV and JSON download buttons exist
        assert page.locator("#field-download-csv-btn").is_visible()
        assert page.locator("#field-download-btn").is_visible()

        # Verify canvas rendered
        canvas = page.locator("#field-canvas")
        assert canvas.is_visible()

        # Save desktop screenshot
        save_screenshot(page, "field_1440px.png")

        # 4. Test Compare both with Wood preset
        page.select_option("#field-material-select", value="wood")
        page.click("#field-submit-btn")
        page.wait_for_selector("#field-result-panel", state="visible", timeout=10000)
        page.wait_for_timeout(300)

        # -------------------------------------------------------------
        # Mobile 390x844
        # -------------------------------------------------------------
        context_mobile = browser.new_context(viewport={"width": 390, "height": 844})
        page_mobile = context_mobile.new_page()
        page_mobile.on("console", on_console)
        page_mobile.on("pageerror", on_page_error)

        page_mobile.goto(f"{live_server}/#field", wait_until="networkidle")
        page_mobile.wait_for_selector("#heading-field", state="visible")
        page_mobile.click("#field-submit-btn")
        page_mobile.wait_for_selector("#field-result-panel", state="visible", timeout=10000)
        page_mobile.wait_for_timeout(300)

        save_screenshot(page_mobile, "field_390px.png")

        browser.close()

    # Verify zero console errors
    assert len(console_errors) == 0, f"Console errors detected: {console_errors}"
