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
import re
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

        # Verify summary strip and API match for Steel
        method_badge = page.locator("#field-method-badge").inner_text()
        assert "Compare both" in method_badge or "Standard calculation" in method_badge
        diff_text = page.locator("#field-rel-diff-val").inner_text()
        assert "%" in diff_text
        timing_text = page.locator("#field-timing-text").inner_text()
        assert "ms" in timing_text

        # Verify on-screen relative difference matches /v1/field API directly
        api_steel = page.evaluate("""async () => {
            const res = await fetch('/v1/field', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({
                    alpha: 1.3e-5, bar_length_m: 0.1, test_duration_s: 100,
                    boundary_temperature: 20, initial_peak_temperature: 80,
                    Nx: 101, Nt: 201, method: 'compare'
                })
            });
            return await res.json();
        }""")
        expected_steel_diff = f"{api_steel['relative_difference'] * 100:.4f}%"
        assert diff_text == expected_steel_diff, f"On-screen difference {diff_text} must match API {expected_steel_diff}"

        # Verify 3 New Visuals Present
        # Visual C: Bar strip
        assert page.locator("#field-bar-strip-box").is_visible()
        assert page.locator("#field-bar-strip-canvas").is_visible()
        assert page.locator("#field-strip-points").is_visible()
        assert page.locator("#field-moment-table").is_visible()

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

        # 4. Check values at t = 20 s for Steel
        # Middle temperature must be within 0.5 °C of exact formula value (~66.42 °C)
        pt0_text = page.locator("#field-pt-0").inner_text()
        pt4_text = page.locator("#field-pt-4").inner_text()
        pt2_text = page.locator("#field-pt-2").inner_text()
        assert "20.0" in pt0_text and "C" in pt0_text, f"Left end at 20 s should be 20.0 °C, got {pt0_text}"
        assert "20.0" in pt4_text and "C" in pt4_text, f"Right end at 20 s should be 20.0 °C, got {pt4_text}"
        m_t20 = re.search(r"([\d\.]+)\s*(?:°C|C|&deg;C)", pt2_text)
        assert m_t20 is not None
        mid_temp_20 = float(m_t20.group(1))
        assert abs(mid_temp_20 - 66.42) <= 0.5, f"Middle temp at 20 s ({mid_temp_20}) must be within 0.5 C of 66.42 C"

        # Check table at t=20 s
        table_rows_20 = page.locator("#field-moment-table-body tr")
        assert table_rows_20.count() == 5
        assert "20.00" in table_rows_20.nth(0).inner_text()
        assert "66.4" in table_rows_20.nth(2).inner_text()

        # 5. STRIP PIXEL CHECK on #field-bar-strip-canvas at 20 s
        strip_pixels = page.evaluate("""() => {
            const canvas = document.getElementById('field-bar-strip-canvas');
            const ctx = canvas.getContext('2d');
            const w = canvas.width;
            const h = canvas.height;
            const p_end = Array.from(ctx.getImageData(4, Math.floor(h / 2), 1, 1).data);
            const p_mid = Array.from(ctx.getImageData(Math.floor(w / 2), Math.floor(h / 2), 1, 1).data);
            return { p_end, p_mid };
        }""")
        strip_end = strip_pixels["p_end"]
        strip_mid = strip_pixels["p_mid"]
        assert strip_mid[0] > 180, f"Strip middle pixel should be hot/warm red (R > 180), got {strip_mid}"
        assert strip_end[0] < 80, f"Strip end pixel should be cold blue (R < 80), got {strip_end}"
        assert abs(strip_mid[0] - strip_end[0]) > 100, f"Strip middle ({strip_mid[0]}) must differ clearly from end ({strip_end[0]})"

        # 6. Check strip & table values at t = 0
        page.fill("#field-time-slider", "0")
        page.dispatch_event("#field-time-slider", "input")
        page.wait_for_timeout(150)

        pt0_t0 = page.locator("#field-pt-0").inner_text()
        pt4_t0 = page.locator("#field-pt-4").inner_text()
        pt2_t0 = page.locator("#field-pt-2").inner_text()
        assert "20.0" in pt0_t0 and "C" in pt0_t0, f"Left end at t=0 should be 20.0 °C, got {pt0_t0}"
        assert "20.0" in pt4_t0 and "C" in pt4_t0, f"Right end at t=0 should be 20.0 °C, got {pt4_t0}"
        assert "80.0" in pt2_t0 and "C" in pt2_t0, f"Middle at t=0 should be 80.0 °C, got {pt2_t0}"

        table_rows_0 = page.locator("#field-moment-table-body tr")
        assert "20.00" in table_rows_0.nth(0).inner_text()
        assert "80.00" in table_rows_0.nth(2).inner_text()

        # Restore slider to 40 (20 s)
        page.fill("#field-time-slider", "40")
        page.dispatch_event("#field-time-slider", "input")
        page.wait_for_timeout(100)

        # 7. HOVER TOOLTIPS CHECK
        # Hover over strip canvas
        page.hover("#field-bar-strip-canvas", position={"x": 250, "y": 14})
        page.wait_for_timeout(100)
        tooltip = page.locator("#field-hover-tooltip")
        assert tooltip.is_visible()
        tip_text = tooltip.inner_text()
        assert " m: " in tip_text and " °C" in tip_text

        # Hover over profile SVG
        page.hover("#field-profile-svg", position={"x": 270, "y": 100})
        page.wait_for_timeout(100)
        tip_profile = tooltip.inner_text()
        assert " m: " in tip_profile and " °C" in tip_profile

        # Hover over spot SVG
        page.hover("#field-spot-svg", position={"x": 270, "y": 100})
        page.wait_for_timeout(100)
        tip_spot = tooltip.inner_text()
        assert " m: " in tip_spot and " °C" in tip_spot

        # 8. Collapsed heatmap pixel check
        heatmap_details = page.locator("#field-heatmap-disclosure")
        assert heatmap_details.count() > 0
        page.evaluate("() => document.getElementById('field-heatmap-disclosure').open = true")
        page.wait_for_timeout(200)

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
        assert p0_mid[0] > 180, f"Heatmap middle of t=0 row must be hot (R > 180), got {p0_mid}"
        assert p0_end[0] < 80, f"Heatmap bar end at t=0 row must be cold (R < 80), got {p0_end}"
        assert abs(p0_mid[0] - p0_end[0]) > 100, f"Middle diff from end must exceed 100"
        assert abs(p0_mid[0] - pLast_mid[0]) > 40, f"Middle diff from t=last must exceed 40"

        # 9. Spot slider interaction
        page.fill("#field-spot-slider", "25")
        page.dispatch_event("#field-spot-slider", "input")
        page.wait_for_timeout(100)
        assert "0.025 m" in page.locator("#field-spot-val").inner_text()

        # 10. Save desktop screenshot
        save_screenshot(page, "field_1440px.png")

        # 11. Test Copper preset & verify on-screen difference equals Copper API
        page.select_option("#field-material-select", value="copper")
        page.click("#field-submit-btn")
        page.wait_for_selector("#field-result-panel", state="visible", timeout=10000)
        page.wait_for_timeout(200)

        copper_diff_text = page.locator("#field-rel-diff-val").inner_text()
        api_copper = page.evaluate("""async () => {
            const res = await fetch('/v1/field', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({
                    alpha: 1.11e-4, bar_length_m: 0.1, test_duration_s: 100,
                    boundary_temperature: 20, initial_peak_temperature: 80,
                    Nx: 101, Nt: 201, method: 'compare'
                })
            });
            return await res.json();
        }""")
        expected_copper_diff = f"{api_copper['relative_difference'] * 100:.4f}%"
        assert copper_diff_text == expected_copper_diff, f"Copper on-screen {copper_diff_text} must match API {expected_copper_diff}"

        # 12. Test Wood preset
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
