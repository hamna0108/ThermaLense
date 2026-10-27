"""Playwright smoke test for Poisson 2D Steady Heat Map customer-friendly rewrite.

Verifies:
1. Loads #poisson with plain labels:
   - "What this page does" 3-line intro box above form
   - Default shape is "Hot spots" with "Single center heat spot"
   - Default example runs automatically so results show immediately
   - "Test pattern (has an exact answer)" button replaces "Wave pattern"
   - Field help texts on Hot spots (Center X/Y, Source strength, Width) and Test pattern
   - Right panel order:
     (a) One-sentence summary generated from numbers
     (b) Steady plate temperature maps with shared colour bar (and difference maps)
     (c) Accuracy table with timing footnote in Show details
     (d) Always-visible honesty note
     (e) Collapsible benchmark disclosure ("Show full benchmark")
2. Colour scale:
   - For Hot spots (non-negative exact solution): one-sided white-to-red scale with maximum labelled.
   - For Test pattern (sine): diverging blue/red scale with both warm and cool lobes.
3. Form synchronization test: selecting each example switches family, visible fields, and highlights active button.
4. Captures clean full-page screenshots at 1440px and 390px.
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


def check_canvas_warm_and_cool(page, canvas_id):
    """Verify that a canvas contains both a warm pixel (R>180, B<120) and a cool pixel (B>180, R<120)."""
    pixel_stats = page.evaluate(f"""() => {{
        const canvas = document.getElementById('{canvas_id}');
        if (!canvas) return null;
        const ctx = canvas.getContext('2d');
        const img = ctx.getImageData(0, 0, canvas.width, canvas.height);
        const data = img.data;
        let warmCount = 0;
        let coolCount = 0;
        let maxR = 0, maxB = 0;
        for (let i = 0; i < data.length; i += 4) {{
            const r = data[i];
            const g = data[i + 1];
            const b = data[i + 2];
            if (r > maxR) maxR = r;
            if (b > maxB) maxB = b;
            if (r > 180 && b < 120) warmCount++;
            if (b > 180 && r < 120) coolCount++;
        }}
        return {{ warmCount, coolCount, maxR, maxB, total: data.length / 4 }};
    }}""")

    assert pixel_stats is not None, f"Canvas {canvas_id} not found"
    assert pixel_stats["warmCount"] > 0, (
        f"Canvas {canvas_id} has no warm pixels: {pixel_stats}"
    )
    assert pixel_stats["coolCount"] > 0, (
        f"Canvas {canvas_id} has no cool pixels: {pixel_stats}"
    )
    return pixel_stats


def test_poisson_smoke_wave_and_hotspots(live_server):
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

        # 1. Load Poisson Page
        page.goto(f"{live_server}/#poisson", wait_until="networkidle")
        page.wait_for_selector("#heading-poisson", state="visible")
        assert page.locator("#heading-poisson").inner_text() == "Steady Heat Map (2D)"

        # Check "What this page does" intro box (Requirement 2)
        intro_box = page.locator("#poi-intro-box")
        assert intro_box.is_visible()
        intro_text = intro_box.inner_text()
        assert "A flat plate with its four edges held cold, and heaters on it." in intro_text
        assert "Tell us where the heat comes from; we show where the plate settles (hot near the heaters, cooler toward the edges)." in intro_text
        assert "We solve it three ways and compare." in intro_text
        assert "Values are relative, not real degrees." in intro_text

        # Check default shape is "Heaters" and example is "Single center heat spot" (Requirement 1)
        gauss_btn = page.locator("#poi-family-gauss-btn")
        sine_btn = page.locator("#poi-family-sine-btn")
        assert "active" in gauss_btn.get_attribute("class")
        assert "active" not in sine_btn.get_attribute("class")
        assert "Test pattern" in sine_btn.inner_text()
        assert "Heaters" in gauss_btn.inner_text()
        assert page.locator("#poi-family-desc").inner_text() == "Round heat sources you place on the plate."

        preset_select = page.locator("#poi-presets-select")
        assert preset_select.input_value() == "gauss_center"
        preset_options = page.locator("#poi-presets-select option").all_inner_texts()
        assert "Test pattern, 2 x 2 zones" in preset_options
        assert page.locator("#poi-gauss-controls").is_visible()
        assert not page.locator("#poi-sine-controls").is_visible()

        # Check field help text for Hot spots (Requirement 6)
        cx_help = page.locator("label[for='poi-gauss-cx'] + input + span.form-help").inner_text()
        assert "Where the heater sits (0 = left or bottom edge, 1 = right or top edge, 0.5 = middle)" in cx_help
        amp_help = page.locator("label[for='poi-gauss-amp'] + input + span.form-help").inner_text()
        assert "How powerful the heater is" in amp_help
        sigma_help = page.locator("label[for='poi-gauss-sigma'] + input + span.form-help").inner_text()
        assert "How spread out the heat is (small = sharp spot, large = broad)" in sigma_help

        # Check Detail (grid size) Show details (Requirement 3)
        more_opts = page.locator("#poi-more-options > summary")
        assert more_opts.is_visible()
        more_opts.click()
        assert page.locator("text=Detail (grid size)").is_visible()
        grid_details = page.locator("#poi-more-options details")
        assert grid_details.is_visible()
        grid_details.locator("> summary").click()
        assert "Pre-factorized direct solver initialized at 64" in grid_details.inner_text()
        more_opts.click()  # close back

        # Requirement 1: Results show automatically on page open without clicking submit!
        page.wait_for_selector("#poi-result-panel", state="visible", timeout=15000)

        # Requirement 3: Right panel order verification
        # (a) One-sentence summary generated from the numbers
        summary_callout = page.locator("#poi-summary-callout")
        assert summary_callout.is_visible()
        summary_text = page.locator("#poi-summary-text").inner_text()
        assert "The plate is warmest at the heater and cools toward the edges." in summary_text
        assert "All three methods agree closely" in summary_text
        assert "(exact 0%, AI model" in summary_text
        assert "simple baseline" in summary_text

        # (b) Solution maps and shared colour bar
        assert page.locator("#poi-solution-colorbar").is_visible()
        assert page.locator("h4", has_text="Exact answer").is_visible()
        assert page.locator("h4", has_text="AI model's answer").is_visible()
        assert page.locator("h4", has_text="Simple baseline's answer").is_visible()

        # Requirement 5: For non-negative exact solution, one-sided white-to-red scale with maximum labelled
        scale_min_text = page.locator("#poi-scale-min").inner_text()
        scale_max_text = page.locator("#poi-scale-max").inner_text()
        assert "0.000 (edges)" in scale_min_text
        assert "(max)" in scale_max_text

        # Difference maps
        assert page.locator("h3", has_text="Difference from exact").is_visible()
        assert page.locator("#poi-diff-colorbar").is_visible()
        assert page.locator("h4", has_text="AI model: difference from exact").is_visible()
        assert page.locator("h4", has_text="Simple baseline: difference from exact").is_visible()

        # (c) Accuracy table
        table_headers = page.locator("#poi-result-panel table").first.locator("thead th").all_inner_texts()
        assert "Calculation" in table_headers
        assert "Error vs exact (%)" in table_headers
        assert "Time taken (ms)" in table_headers

        rows_text = page.locator("#poi-result-panel table").first.locator("tbody").inner_text()
        assert "Exact solver (reference)" in rows_text
        assert "Simple baseline (linear model)" in rows_text
        assert "AI model (neural network)" in rows_text

        # Timing note in Show details under table
        timing_details = page.locator("#poi-timing-details")
        assert timing_details.is_visible()
        timing_details.locator("summary").click()
        assert "Timings show end-to-end server calculation" in timing_details.inner_text()

        # (d) Honesty note
        honesty_note = page.locator("#poi-honesty-note")
        assert honesty_note.is_visible()
        assert "Across our full test sets the simple baseline was as accurate or better on every test split." in honesty_note.inner_text()

        # (e) Collapsible full benchmark disclosure
        benchmark_disc = page.locator("#poi-benchmark-disclosure")
        assert benchmark_disc.is_visible()
        assert not benchmark_disc.evaluate("el => el.open")  # collapsed by default

        # 2. Switch to Test pattern 2x2 (diverging wave pattern)
        page.select_option("#poi-presets-select", "sine_low")
        assert page.locator("#poi-sine-controls").is_visible()
        assert not page.locator("#poi-gauss-controls").is_visible()
        assert "active" in sine_btn.get_attribute("class")
        assert "active" not in gauss_btn.get_attribute("class")
        assert page.locator("#poi-family-desc").inner_text() == "Alternating warm and cool zones, used to check accuracy."

        # Check field help text for Test pattern
        m_help = page.locator("label[for='poi-mode-m'] + input + span.form-help").inner_text()
        assert "Number of hot and cool waves horizontally" in m_help

        page.click("#poi-submit-btn")
        page.wait_for_selector("#poi-result-panel", state="visible", timeout=15000)

        # Requirement 2: Summary wording for Test pattern
        summary_sine = page.locator("#poi-summary-text").inner_text()
        assert "The plate has warm and cool zones, as the pattern asks." in summary_sine
        assert "(exact 0%, AI model 2.9%, simple baseline 4.6%)" in summary_sine

        # Requirement 5: For sine wave with negative values, diverging scale used
        scale_min_div = page.locator("#poi-scale-min").inner_text()
        assert "(cooler than edges)" in scale_min_div

        # PIXEL CHECK on diverging solution: both warm and cool lobes present
        stats_exact = check_canvas_warm_and_cool(page, "poi-canvas-exact")
        stats_fno = check_canvas_warm_and_cool(page, "poi-canvas-fno")
        stats_lin = check_canvas_warm_and_cool(page, "poi-canvas-lin")

        # Save 1440px screenshot
        save_screenshot(page, "poisson_1440px.png")
        context.close()

        # -------------------------------------------------------------
        # Mobile 390x844
        # -------------------------------------------------------------
        mobile_context = browser.new_context(viewport={"width": 390, "height": 844})
        mobile_page = mobile_context.new_page()
        mobile_page.on("console", on_console)
        mobile_page.on("pageerror", on_page_error)

        mobile_page.goto(f"{live_server}/#poisson", wait_until="networkidle")
        mobile_page.wait_for_selector("#heading-poisson", state="visible")
        # Results show automatically on mobile too!
        mobile_page.wait_for_selector("#poi-result-panel", state="visible", timeout=15000)
        time.sleep(0.5)

        save_screenshot(mobile_page, "poisson_390px.png")
        mobile_context.close()

        browser.close()

    assert not console_errors, f"Console errors encountered: {console_errors}"


def test_poisson_example_selection_and_form_sync(live_server):
    """Test Requirement 4: selecting each example updates visible fields and active shape button."""
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 1280, "height": 720})

        page.goto(f"{live_server}/#poisson", wait_until="networkidle")
        page.wait_for_selector("#heading-poisson", state="visible")

        sine_btn = page.locator("#poi-family-sine-btn")
        gauss_btn = page.locator("#poi-family-gauss-btn")
        sine_controls = page.locator("#poi-sine-controls")
        gauss_controls = page.locator("#poi-gauss-controls")

        desc = page.locator("#poi-family-desc")

        # 1. Default on open: gauss_center
        assert "active" in gauss_btn.get_attribute("class")
        assert "active" not in sine_btn.get_attribute("class")
        assert gauss_controls.is_visible()
        assert not sine_controls.is_visible()
        assert desc.inner_text() == "Round heat sources you place on the plate."

        # 2. Select gauss_dual
        page.select_option("#poi-presets-select", "gauss_dual")
        assert "active" in gauss_btn.get_attribute("class")
        assert "active" not in sine_btn.get_attribute("class")
        assert gauss_controls.is_visible()
        assert not sine_controls.is_visible()
        assert desc.inner_text() == "Round heat sources you place on the plate."

        # 3. Select sine_low
        page.select_option("#poi-presets-select", "sine_low")
        assert "active" in sine_btn.get_attribute("class")
        assert "active" not in gauss_btn.get_attribute("class")
        assert sine_controls.is_visible()
        assert not gauss_controls.is_visible()
        assert desc.inner_text() == "Alternating warm and cool zones, used to check accuracy."

        # 4. Select sine_high
        page.select_option("#poi-presets-select", "sine_high")
        assert "active" in sine_btn.get_attribute("class")
        assert "active" not in gauss_btn.get_attribute("class")
        assert sine_controls.is_visible()
        assert not gauss_controls.is_visible()
        assert desc.inner_text() == "Alternating warm and cool zones, used to check accuracy."

        # 5. Direct button clicks switch family and sync controls
        gauss_btn.click()
        assert "active" in gauss_btn.get_attribute("class")
        assert "active" not in sine_btn.get_attribute("class")
        assert gauss_controls.is_visible()
        assert not sine_controls.is_visible()
        assert desc.inner_text() == "Round heat sources you place on the plate."

        sine_btn.click()
        assert "active" in sine_btn.get_attribute("class")
        assert "active" not in gauss_btn.get_attribute("class")
        assert sine_controls.is_visible()
        assert not gauss_controls.is_visible()
        assert desc.inner_text() == "Alternating warm and cool zones, used to check accuracy."

        browser.close()
