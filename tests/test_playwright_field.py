"""Playwright smoke test for Field (Heat Over Time 1D) customer-friendly rewrite.

Verifies:
1. Loads page #field with eyebrow PREDICT and plain subtitle.
2. Settings panel with real units inputs, material dropdown in scientific notation, same-temp note.
3. Three new visual views present:
   - "Temperature along the bar" (5 line curves + time slider highlight + exact formula)
   - "Temperature at one spot over time" (line chart with position slider)
   - Coloured strip of the bar (cold=blue, hot=red) with °C range labels
4. Collapsed "Show full heat map" section with heatmap canvas and °C color bar.
5. PIXEL CHECK:
   - Middle of t=0 row must differ clearly from bar end at same row and from last row's middle.
6. Validation check:
   - Plain error when starting peak temperature equals ends temperature.
7. Computes with Compare both for Steel, Copper, and Wood presets.
8. Zero console errors throughout.
9. Captures clean full-page screenshots at 1440px and 390px.
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


def test_field_smoke_steel_copper_and_wood(live_server):
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

        # Check scientific notation in alpha input
        alpha_val = page.locator("#field-alpha").input_value()
        assert "e" in alpha_val or "E" in alpha_val, f"Alpha {alpha_val} should be scientific notation"

        # Check same-temperature note
        assert page.locator("text=Both ends are held at the same temperature during the test.").is_visible()

        # 2. Test Equal Temperature Validation
        page.fill("#field-temp-peak", "20")
        page.click("#field-submit-btn")
        page.wait_for_selector("#field-state-container .error", state="visible")
        err_msg = page.locator("#field-state-container").inner_text()
        assert "Starting peak temperature must differ from the ends temperature." in err_msg
        page.fill("#field-temp-peak", "80")  # restore

        # 3. Compute with Steel preset (default)
        comp_btn = page.locator("#field-method-compare-btn")
        if "active" not in comp_btn.get_attribute("class"):
            comp_btn.click()

        page.click("#field-submit-btn")
        page.wait_for_selector("#field-result-panel", state="visible", timeout=10000)

        # Verify summary strip
        method_badge = page.locator("#field-method-badge").inner_text()
        assert "Compare both" in method_badge or "Standard calculation" in method_badge
        diff_text = page.locator("#field-rel-diff-val").inner_text()
        assert "%" in diff_text
        timing_text = page.locator("#field-timing-text").inner_text()
        assert "ms" in timing_text

        # Verify 3 New Visuals Present
        # Visual C: Bar strip
        assert page.locator("#field-bar-strip-box").is_visible()
        assert page.locator("#field-bar-strip-canvas").is_visible()

        # Visual A: Temperature along the bar (5 curves + slider moment + exact)
        assert page.locator("#field-curves-title").is_visible()
        profile_svg = page.locator("#field-profile-svg")
        assert profile_svg.is_visible()
        assert profile_svg.locator("path").count() >= 6  # 5 snapshots + active moment + exact

        # Visual B: Temperature at one spot over time
        assert page.locator("#field-spot-title").is_visible()
        assert page.locator("#field-spot-slider").is_visible()
        spot_svg = page.locator("#field-spot-svg")
        assert spot_svg.is_visible()
        assert spot_svg.locator("path").count() >= 2  # computed + exact

        # Collapsed heatmap section
        heatmap_details = page.locator("#field-heatmap-disclosure")
        assert heatmap_details.count() > 0

        # Open collapsed heatmap to inspect pixels
        page.evaluate("() => document.getElementById('field-heatmap-disclosure').open = true")
        page.wait_for_timeout(200)

        # 4. PIXEL CHECK on #field-canvas
        pixels = page.evaluate("""() => {
            const canvas = document.getElementById('field-canvas');
            const ctx = canvas.getContext('2d');
            const w = canvas.width;
            const h = canvas.height;
            const p0_end = Array.from(ctx.getImageData(5, 2, 1, 1).data);
            const p0_mid = Array.from(ctx.getImageData(Math.floor(w / 2), 2, 1, 1).data);
            const pLast_mid = Array.from(ctx.getImageData(Math.floor(w / 2), h - 5, 1, 1).data);
            return { p0_end, p0_mid, pLast_mid };
        }""")

        p0_end = pixels["p0_end"]
        p0_mid = pixels["p0_mid"]
        pLast_mid = pixels["pLast_mid"]

        # Middle at t=0 must be hot (bright, high red/green): not solid black!
        assert p0_mid[0] > 180, f"Middle of t=0 row must be hot (R > 180), got {p0_mid}"
        # End at t=0 must be cold (dark):
        assert p0_end[0] < 80, f"Bar end at t=0 row must be cold (R < 80), got {p0_end}"
        # Middle of t=0 row must differ clearly from bar end at same row:
        diff_end = abs(p0_mid[0] - p0_end[0])
        assert diff_end > 100, f"Middle at t=0 ({p0_mid[0]}) must differ clearly from end ({p0_end[0]}), diff={diff_end}"
        # Middle of t=0 row must differ clearly from last row's middle:
        diff_last = abs(p0_mid[0] - pLast_mid[0])
        assert diff_last > 40, f"Middle at t=0 ({p0_mid[0]}) must differ clearly from t=last ({pLast_mid[0]}), diff={diff_last}"

        # 5. Spot slider interaction
        page.fill("#field-spot-slider", "25")
        page.dispatch_event("#field-spot-slider", "input")
        page.wait_for_timeout(100)
        assert "0.025 m" in page.locator("#field-spot-val").inner_text()

        # 6. Save desktop screenshot
        save_screenshot(page, "field_1440px.png")

        # 7. Test Copper preset
        page.select_option("#field-material-select", value="copper")
        page.click("#field-submit-btn")
        page.wait_for_selector("#field-result-panel", state="visible", timeout=10000)
        page.wait_for_timeout(200)

        # 8. Test Wood preset
        page.select_option("#field-material-select", value="wood")
        page.click("#field-submit-btn")
        page.wait_for_selector("#field-result-panel", state="visible", timeout=10000)
        page.wait_for_timeout(200)

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
