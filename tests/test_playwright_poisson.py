"""Playwright smoke test for Poisson 2D Steady Heat Map customer-friendly rewrite.

Verifies:
1. Loads #poisson with plain labels:
   - "Show steady temperature" button
   - "Source strength", "Detail (grid size)" under More options
   - Plain examples ("Wave pattern 2x2 (typical)", etc.)
   - Plain table headers: "Calculation", "Error vs exact (%)", "Time taken (ms)"
   - Plain method names: "Exact solver (reference)", "Simple baseline (linear model)", "AI model (neural network)"
   - Badges: "Reference", "Simple baseline", "AI model: inside its trained range"
   - Panel titles: "Exact answer", "AI model's answer", "Simple baseline's answer"
   - Difference maps: "Difference from exact", "AI model: difference from exact", "Simple baseline: difference from exact"
   - Axis labels: "Position across the plate", "Position up the plate"
   - Always-visible honesty note
   - Collapsible benchmark disclosure ("Show full benchmark")
   - Timing note
2. Computes Wave pattern 2x2:
   - Error formatted as percentage (e.g. 2.9%, not 0.029476)
   - PIXEL CHECK on all 3 maps: each must have BOTH warm (R>180, B<120) and cool (B>180, R<120) regions.
3. Computes Hot spots preset (Gaussian).
4. Zero console errors throughout.
5. Captures clean full-page screenshots at 1440px and 390px.
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

        # Check plain labels
        submit_btn = page.locator("#poi-submit-btn")
        assert "Show steady temperature" in submit_btn.text_content()

        # Check Source strength label
        amp_label = page.locator("label[for='poi-mode-amp']").text_content().strip()
        assert amp_label == "Source strength"

        # Check Detail (grid size) moved under More options
        more_opts = page.locator("#poi-more-options summary")
        assert more_opts.is_visible()
        more_opts.click()
        assert page.locator("text=Detail (grid size)").is_visible()
        more_opts.click()  # close back

        # Check plain preset option names
        preset_options = page.locator("#poi-presets-select option").all_inner_texts()
        assert "Wave pattern 2x2 (typical)" in preset_options
        assert "Wave pattern 6x2 (high frequency)" in preset_options
        assert "Single center heat spot" in preset_options
        assert "Dual heat spots" in preset_options

        # 2. Run Wave pattern 2x2 calculation
        page.click("#poi-submit-btn")
        page.wait_for_selector("#poi-result-panel", state="visible", timeout=15000)

        # Verify table column headers
        table_headers = page.locator("#poi-result-panel table").first.locator("thead th").all_inner_texts()
        assert "Calculation" in table_headers
        assert "Error vs exact (%)" in table_headers
        assert "Time taken (ms)" in table_headers

        # Verify plain calculation labels in table rows
        rows_text = page.locator("#poi-result-panel table").first.locator("tbody").inner_text()
        assert "Exact solver (reference)" in rows_text
        assert "Simple baseline (linear model)" in rows_text
        assert "AI model (neural network)" in rows_text

        # Verify errors shown as percent (e.g. "2.9%", not "0.029476")
        fno_err_text = page.locator("#poi-err-fno").inner_text().strip()
        assert "%" in fno_err_text, f"FNO error '{fno_err_text}' should contain '%'"
        assert not fno_err_text.startswith("0.029"), f"FNO error '{fno_err_text}' should not be raw float"

        lin_err_text = page.locator("#poi-err-lin").inner_text().strip()
        assert "%" in lin_err_text, f"Linear baseline error '{lin_err_text}' should contain '%'"

        # Verify Badges
        assert page.locator("#poi-badge-lin").inner_text() == "Simple baseline"
        assert page.locator("#poi-badge-fno").inner_text() == "AI model: inside its trained range"

        # Verify Panel Titles
        assert page.locator("h4", has_text="Exact answer").is_visible()
        assert page.locator("h4", has_text="AI model's answer").is_visible()
        assert page.locator("h4", has_text="Simple baseline's answer").is_visible()

        # Verify Difference titles
        assert page.locator("h3", has_text="Difference from exact").is_visible()
        assert page.locator("h4", has_text="AI model: difference from exact").is_visible()
        assert page.locator("h4", has_text="Simple baseline: difference from exact").is_visible()

        # Verify Axis labels
        assert page.locator("text=Position across the plate").count() >= 3
        assert page.locator("text=Position up the plate").count() >= 3

        # Verify Honesty note (always visible)
        honesty_note = page.locator("#poi-honesty-note")
        assert honesty_note.is_visible()
        assert "In this example the AI model is closer to the exact answer. Across our full test sets the simple baseline was as accurate or better on every test split." in honesty_note.inner_text()

        # Verify Collapsible full benchmark disclosure
        benchmark_disc = page.locator("#poi-benchmark-disclosure")
        assert benchmark_disc.is_visible()
        disc_text = benchmark_disc.text_content()
        assert "Show full benchmark" in disc_text
        assert "Standard test (interpolation)" in disc_text
        assert "Rapid wave changes (high frequencies)" in disc_text
        bench_headers = [t.strip() for t in benchmark_disc.locator("thead th").all_text_contents()]
        assert "Simple baseline (median rel L₂ error, %)" in bench_headers
        assert "AI model (median rel L₂ error, %)" in bench_headers

        # Verify Timing note
        timing_note = page.locator("#poi-timing-note")
        assert timing_note.is_visible()
        assert "Timings show end-to-end server calculation" in timing_note.inner_text()

        # 3. PIXEL CHECK: Wave pattern 2x2 must have BOTH warm and cool lobes in all 3 maps
        stats_exact = check_canvas_warm_and_cool(page, "poi-canvas-exact")
        stats_fno = check_canvas_warm_and_cool(page, "poi-canvas-fno")
        stats_lin = check_canvas_warm_and_cool(page, "poi-canvas-lin")

        # Save 1440px screenshot
        save_screenshot(page, "poisson_1440px.png")

        # 4. Test Hot spots preset (Gaussian)
        page.click("#poi-family-gauss-btn")
        assert page.locator("#poi-gauss-controls").is_visible()
        page.click("#poi-submit-btn")
        page.wait_for_selector("#poi-result-panel", state="visible")
        # Ensure dynamic data-driven update on Gaussian where simple baseline is closer
        assert "In this example the simple baseline is closer. Across our full test sets the simple baseline was as accurate or better on every test split." in honesty_note.inner_text()
        time.sleep(0.5)

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
        mobile_page.click("#poi-submit-btn")
        mobile_page.wait_for_selector("#poi-result-panel", state="visible")
        time.sleep(0.5)

        save_screenshot(mobile_page, "poisson_390px.png")
        mobile_context.close()

        browser.close()

    assert not console_errors, f"Console errors encountered: {console_errors}"
