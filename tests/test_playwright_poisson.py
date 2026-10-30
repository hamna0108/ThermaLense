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
        assert "0 = left or bottom edge, 1 = right or top edge" in cx_help
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

        # Verify results do not show on start; only when Show steady temperature is clicked
        assert not page.locator("#poi-result-panel").is_visible()
        assert "Configure the heat source and click" in page.locator("#poi-state-container").inner_text()
        page.click("#poi-submit-btn")
        page.wait_for_selector("#poi-result-panel", state="visible", timeout=15000)

        # Requirement: Card title and intro line
        assert page.locator("#poisson-results-card .card-title").inner_text() == "Plate temperature"
        assert "Top-down view of the plate. White is cold (edges stay at 0), red is hot. The hottest spot is where your heater is." in page.locator("#poi-card-intro").inner_text()

        # (a) Segmented View Buttons
        btn_result = page.locator("#poi-view-btn-result")
        btn_fno = page.locator("#poi-view-btn-fno")
        btn_lin = page.locator("#poi-view-btn-lin")
        btn_compare = page.locator("#poi-view-btn-compare")

        assert btn_result.is_visible()
        assert btn_fno.is_visible()
        assert btn_lin.is_visible()
        assert btn_compare.is_visible()

        # Result is selected by default and visually active
        assert "active" in btn_result.get_attribute("class")
        assert btn_result.get_attribute("aria-selected") == "true"
        assert "active" not in btn_fno.get_attribute("class")

        # (b) Single view for Result (Exact solver)
        single_view = page.locator("#poi-single-view")
        compare_view = page.locator("#poi-compare-view")
        assert single_view.is_visible()
        assert not compare_view.is_visible()

        assert "exact answer" in page.locator("#poi-single-title").inner_text().lower()
        single_box = page.locator("#poi-canvas-single").bounding_box()
        assert single_box["width"] >= 240, f"Expected single canvas to be large, got {single_box['width']}"
        assert page.locator("#poi-solution-colorbar").is_visible()

        hottest_text = page.locator("#poi-hottest-point").inner_text()
        assert "Hottest point:" in hottest_text
        assert "in plate units" in hottest_text

        caption_text = page.locator("#poi-single-caption").inner_text()
        assert caption_text == "Exact solver (the reference answer)"
        assert not page.locator("#poi-single-amber-warning").is_visible()

        # Requirement: For non-negative exact solution, one-sided white-to-red scale with maximum labelled
        scale_min_text = page.locator("#poi-scale-min").inner_text()
        scale_max_text = page.locator("#poi-scale-max").inner_text()
        assert "0.000 (edges)" in scale_min_text
        assert "(max)" in scale_max_text

        # (c) Test switching to AI model single view without recomputing
        btn_fno.click()
        assert "active" in btn_fno.get_attribute("class")
        assert "active" not in btn_result.get_attribute("class")
        assert "ai model" in page.locator("#poi-single-title").inner_text().lower()
        assert "different from the exact answer" in page.locator("#poi-single-caption").inner_text()
        assert "Hottest point:" in page.locator("#poi-hottest-point").inner_text()

        # (d) Test switching to Simple baseline single view without recomputing
        btn_lin.click()
        assert "active" in btn_lin.get_attribute("class")
        assert "simple baseline" in page.locator("#poi-single-title").inner_text().lower()
        assert "different from the exact answer" in page.locator("#poi-single-caption").inner_text()
        assert "Hottest point:" in page.locator("#poi-hottest-point").inner_text()

        # (e) Test switching to Compare view
        btn_compare.click()
        assert "active" in btn_compare.get_attribute("class")
        assert not single_view.is_visible()
        assert compare_view.is_visible()

        # Three plates side by side with equal-height titles
        box_exact = page.locator("#poi-canvas-exact").bounding_box()
        box_fno = page.locator("#poi-canvas-fno").bounding_box()
        box_lin = page.locator("#poi-canvas-lin").bounding_box()
        assert abs(box_exact["y"] - box_fno["y"]) < 1.0, f"Compare Exact ({box_exact['y']}) and FNO ({box_fno['y']}) misaligned"
        assert abs(box_exact["y"] - box_lin["y"]) < 1.0, f"Compare Exact ({box_exact['y']}) and Lin ({box_lin['y']}) misaligned"

        # Plain line above difference maps
        assert "White means a match and red means a bigger difference. The differences are tiny compared with the plate temperature." in compare_view.inner_text()

        # Difference maps inside Compare view
        assert page.get_by_role("heading", name="Difference from exact", exact=True).is_visible()
        assert page.locator("#poi-diff-colorbar").is_visible()
        assert page.locator("h4", has_text="AI model: difference from exact").is_visible()
        assert page.locator("h4", has_text="Simple baseline: difference from exact").is_visible()

        # Results table inside Compare view
        table_headers = compare_view.locator("table").first.locator("thead th").all_inner_texts()
        assert "Calculation" in table_headers
        assert "Error vs exact (%)" in table_headers
        assert "Time taken (ms)" in table_headers

        rows_text = compare_view.locator("table").first.locator("tbody").inner_text()
        assert "Exact solver (reference)" in rows_text
        assert "Simple baseline (linear model)" in rows_text
        assert "AI model (neural network)" in rows_text

        # Collapsed section "Accuracy check (for experts)" has been removed
        assert page.locator("#poi-accuracy-details").count() == 0

        # Timing note in Show details
        timing_details = page.locator("#poi-timing-details")
        assert timing_details.is_visible()
        timing_details.locator("> summary").click()
        assert "Timings show end-to-end server calculation" in timing_details.inner_text()

        # Switch back to Result
        btn_result.click()
        assert single_view.is_visible()
        assert not compare_view.is_visible()

        # (e) Honesty note
        honesty_note = page.locator("#poi-honesty-note")
        assert honesty_note.is_visible()
        assert "Across our full test sets the simple baseline was as accurate or better on every test split." in honesty_note.inner_text()

        # (f) Collapsible full benchmark disclosure
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

        # Requirement: For sine wave with negative values, diverging scale used
        scale_min_div = page.locator("#poi-scale-min").inner_text()
        assert "(cooler than edges)" in scale_min_div

        # PIXEL CHECK on diverging solution: both warm and cool lobes present in single view
        stats_single = check_canvas_warm_and_cool(page, "poi-canvas-single")

        # In Compare view, check all 3 compare canvases
        page.click("#poi-view-btn-compare")
        stats_exact = check_canvas_warm_and_cool(page, "poi-canvas-exact")
        stats_fno = check_canvas_warm_and_cool(page, "poi-canvas-fno")
        stats_lin = check_canvas_warm_and_cool(page, "poi-canvas-lin")
        page.click("#poi-view-btn-result")

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
        # Click submit to display results on mobile
        mobile_page.click("#poi-submit-btn")
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


def test_poisson_width_limits_and_alignment(live_server):
    """Test width minimum (0.04), amber warning note, shortened help text, and plate alignment."""
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 1440, "height": 900})

        page.goto(f"{live_server}/#poisson", wait_until="networkidle")
        page.wait_for_selector("#heading-poisson", state="visible")
        page.click("#poi-submit-btn")
        page.wait_for_selector("#poi-result-panel", state="visible", timeout=15000)

        # 1. Helper text for Center X and Center Y
        cx_help = page.locator("label[for='poi-gauss-cx'] + input + span.form-help").inner_text()
        cy_help = page.locator("label[for='poi-gauss-cy'] + input + span.form-help").inner_text()
        assert cx_help == "0 = left or bottom edge, 1 = right or top edge"
        assert cy_help == "0 = left or bottom edge, 1 = right or top edge"

        # 2. Panel alignment: in Compare view, the three plates have aligned top positions
        page.click("#poi-view-btn-compare")
        box_exact = page.locator("#poi-canvas-exact").bounding_box()
        box_fno = page.locator("#poi-canvas-fno").bounding_box()
        box_lin = page.locator("#poi-canvas-lin").bounding_box()
        assert abs(box_exact["y"] - box_fno["y"]) < 1.0, f"Exact ({box_exact['y']}) and FNO ({box_fno['y']}) misaligned"
        assert abs(box_exact["y"] - box_lin["y"]) < 1.0, f"Exact ({box_exact['y']}) and Lin ({box_lin['y']}) misaligned"
        page.click("#poi-view-btn-result")

        # 3. Width input minimum attribute
        sigma_input = page.locator("#poi-gauss-sigma")
        assert sigma_input.get_attribute("min") == "0.04"

        # 4. Input below 0.04 is clamped to 0.04 and triggers the amber warning note
        sigma_input.fill("0.01")
        page.click("#poi-submit-btn")
        page.wait_for_selector("#poi-result-panel", state="visible", timeout=15000)

        assert sigma_input.input_value() == "0.04"
        amber_note = page.locator("#poi-narrow-warning")
        assert amber_note.is_visible()
        assert "This heater is narrower than the AI model was trained on, so its answer may be wrong. The exact answer is still correct." in amber_note.inner_text()

        # 5. Setting width back to normal training range (>= 0.08) hides amber warning
        sigma_input.fill("0.15")
        page.click("#poi-submit-btn")
        page.wait_for_selector("#poi-result-panel", state="visible", timeout=15000)
        assert not amber_note.is_visible()

        # 6. Check AI view shows amber note when error > 50% (sine_high has > 60% error)
        page.select_option("#poi-presets-select", "sine_high")
        page.click("#poi-submit-btn")
        page.wait_for_selector("#poi-result-panel", state="visible", timeout=15000)

        page.click("#poi-view-btn-fno")
        ai_warning = page.locator("#poi-single-amber-warning")
        assert ai_warning.is_visible()
        assert "The AI model is not reliable for this input." in ai_warning.inner_text()

        # Switch back to Result and verify amber note is hidden
        page.click("#poi-view-btn-result")
        assert not ai_warning.is_visible()

        browser.close()
