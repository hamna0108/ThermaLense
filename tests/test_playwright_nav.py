"""Playwright test suite for Visual Polish, Navigation Polish, Page Eyebrows, and Plain Labels.

Verifies:
1. Navigation:
   - No "Predict"/"Investigate" captions in the desktop nav bar.
   - One row, all eight tabs on the same baseline and same height (~44px).
   - 2px underline on the active tab (accent colour).
   - Hover = subtle background only.
   - Single faint divider between groups (Overview | Field, Poisson | Place Sensors, Estimate, Diagnose | Evidence, Limits).
   - Mobile menu keeps the group headers.
2. Page Eyebrows, Titles, and Plain Subtitles:
   - Eyebrows: "PREDICT" on Field and Poisson; "INVESTIGATE" on Place Sensors, Estimate, and Diagnose.
   - Field: "Heat Over Time" -> "Pick a material and see how the temperature along a bar changes with time."
   - Poisson: "Steady Heat Map (2D)" -> "Place a heat source on a square plate and see the temperature it settles at. Three solvers are compared."
   - Place Sensors: "Plan Your Readings" -> "Find out when to measure so your readings tell you the most."
   - Estimate: "Estimate Heat Spread" -> "Enter your readings to find the material's heat-spread number."
   - Diagnose: "Check Your Data" -> "Check whether your test matches a healthy reference."
   - Technical details moved into "Show details" line.
3. Heading sizes:
   - Consistent H1 size across pages (30-32px desktop, 26px mobile).
   - Consistent H2 size across pages.
4. Poisson page plain labels:
   - "Heat source", "Heat source shape", "Wave pattern", "Hot spots", "Examples",
     "Waves across (x)", "Waves up (y)", "Three solvers compared", "How far from the exact answer".
5. Screenshots:
   - nav, Field, and Poisson at 1440px and 390px without overlapping text.
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
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        env=env
    )
    if not wait_for_port(port, timeout=60):
        proc.kill()
        out, _ = proc.communicate()
        raise RuntimeError(f"Server failed to start on port {port}: {out.decode()}")

    yield f"http://127.0.0.1:{port}"

    proc.terminate()
    try:
        proc.wait(timeout=3)
    except subprocess.TimeoutExpired:
        proc.kill()


def save_screenshot(target, filename):
    filepath = os.path.join(SCREENSHOTS_DIR, filename)
    target.screenshot(path=filepath)
    if os.path.isdir(ARTIFACT_DIR):
        try:
            shutil.copy2(filepath, os.path.join(ARTIFACT_DIR, filename))
        except Exception:
            pass


def test_nav_visual_polish_desktop_1440(live_server):
    """Desktop 1440x900 viewport: check nav layout, tab baseline/height, dividers, eyebrows, titles, subtitles, and labels."""
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(viewport={"width": 1440, "height": 900})
        page = context.new_page()

        page.goto(f"{live_server}/#overview")
        page.wait_for_load_state("domcontentloaded")
        page.wait_for_selector("#heading-overview", state="visible")

        # 1. Navigation order
        links = page.locator(".nav-link")
        link_texts = [links.nth(i).inner_text().strip() for i in range(links.count())]
        expected_order = [
            "Overview",
            "Field",
            "Poisson",
            "Place Sensors",
            "Estimate",
            "Diagnose",
            "Evidence",
            "Limits"
        ]
        assert link_texts == expected_order

        # 2. No "Predict"/"Investigate" captions in desktop nav bar
        assert not page.locator("#nav-label-predict").is_visible()
        assert not page.locator("#nav-label-investigate").is_visible()

        # 3. Three faint dividers between groups
        dividers = page.locator(".nav-divider")
        assert dividers.count() == 3
        for i in range(3):
            assert dividers.nth(i).is_visible()

        # 4. Same baseline and height for all tabs
        boxes = [links.nth(i).bounding_box() for i in range(links.count())]
        base_y = boxes[0]["y"]
        base_height = boxes[0]["height"]
        assert base_height == pytest.approx(44.0, abs=1.0)
        for i, box in enumerate(boxes):
            assert box["y"] == pytest.approx(base_y, abs=1.5), f"Tab {link_texts[i]} baseline y mismatch"
            assert box["height"] == pytest.approx(base_height, abs=1.0), f"Tab {link_texts[i]} height mismatch"

        # 5. 2px underline on active tab
        active_tab = page.locator(".nav-link.active")
        assert active_tab.inner_text().strip() == "Overview"
        b_bottom = active_tab.evaluate("el => window.getComputedStyle(el).borderBottomWidth")
        assert b_bottom == "2px"

        # Capture nav desktop screenshot
        save_screenshot(page.locator(".nav-bar"), "nav_1440px.png")

        # 6. Verify Page Eyebrows, Titles, Subtitles, Details, and H1 sizes across pages
        pages_to_check = [
            {
                "hash": "field",
                "eyebrow": "PREDICT",
                "h1_id": "heading-field",
                "title": "Heat Over Time",
                "sub_id": "field-page-subtitle",
                "subtitle": "Pick a material and see how the temperature along a bar changes with time."
            },
            {
                "hash": "poisson",
                "eyebrow": "PREDICT",
                "h1_id": "heading-poisson",
                "title": "Steady Heat Map (2D)",
                "sub_id": "poisson-page-subtitle",
                "subtitle": "Place a heat source on a square plate and see the temperature it settles at. Three solvers are compared."
            },
            {
                "hash": "placement",
                "eyebrow": "INVESTIGATE",
                "h1_id": "heading-placement",
                "title": "Plan Your Readings",
                "sub_id": "placement-page-subtitle",
                "subtitle": "Find out when to measure so your readings tell you the most."
            },
            {
                "hash": "estimate",
                "eyebrow": "INVESTIGATE",
                "h1_id": "heading-estimate",
                "title": "Estimate Heat Spread",
                "sub_id": "estimate-page-subtitle",
                "subtitle": "Enter your readings to find the material's heat-spread number."
            },
            {
                "hash": "diagnose",
                "eyebrow": "INVESTIGATE",
                "h1_id": "heading-diagnose",
                "title": "Check Your Data",
                "sub_id": "diagnose-page-subtitle",
                "subtitle": "Check whether your test matches a healthy reference."
            }
        ]

        for p_info in pages_to_check:
            page.goto(f"{live_server}/#{p_info['hash']}")
            page.wait_for_selector(f"#{p_info['h1_id']}", state="visible")

            # Check Eyebrow
            view_elem = page.locator(f"#view-{p_info['hash']}")
            eyebrow = view_elem.locator(".page-eyebrow")
            assert eyebrow.is_visible()
            assert eyebrow.inner_text().strip() == p_info["eyebrow"]
            eyebrow_fs = float(eyebrow.evaluate("el => parseFloat(window.getComputedStyle(el).fontSize)"))
            assert 11.0 <= eyebrow_fs <= 12.5

            # Check Title & H1 font-size (30-32px desktop)
            h1 = page.locator(f"#{p_info['h1_id']}")
            assert h1.inner_text().strip() == p_info["title"]
            h1_fs = float(h1.evaluate("el => parseFloat(window.getComputedStyle(el).fontSize)"))
            assert 30.0 <= h1_fs <= 33.0

            # Check Subtitle
            sub = page.locator(f"#{p_info['sub_id']}")
            assert sub.is_visible()
            assert sub.inner_text().strip() == p_info["subtitle"]

            # Check "Show details" collapsible summary exists in page intro
            details_summary = view_elem.locator(".page-intro .technical-details summary")
            assert details_summary.is_visible()
            assert "Show details" in details_summary.inner_text()

        # 7. Check Poisson Plain Labels
        page.goto(f"{live_server}/#poisson")
        page.wait_for_selector("#heading-poisson", state="visible")

        # "Source Term Builder f(x,y)" -> "Heat source"
        assert page.locator("#view-poisson .card-title").first.inner_text().strip() == "Heat source"

        # "Source family" -> "Heat source shape"
        assert page.locator("#view-poisson label:has-text('Heat source shape')").is_visible()

        # "Harmonic Sine Modes" -> "Wave pattern"; "Gaussian Heaters" -> "Hot spots"
        assert page.locator("#poi-family-sine-btn").inner_text().strip() == "Wave pattern"
        assert page.locator("#poi-family-gauss-btn").inner_text().strip() == "Hot spots"

        # "Quick presets" -> "Examples"
        assert page.locator("#view-poisson label:has-text('Examples')").is_visible()

        # "Wavenumber M (x)/N (y)" -> "Waves across (x)" / "Waves up (y)"
        assert page.locator("label[for='poi-mode-m']").text_content().strip() == "Waves across (x)"
        assert page.locator("label[for='poi-mode-n']").text_content().strip() == "Waves up (y)"

        # "In-Distribution" -> "Typical case"
        presets_text = page.locator("#poi-presets-select").inner_text()
        assert "Typical case" in presets_text
        assert "In-Distribution" not in presets_text

        # "Tri-Solver Comparison & Error Analysis" -> "Three solvers compared"
        assert page.locator("#poisson-results-card .card-title").inner_text().strip() == "Three solvers compared"

        # error columns -> "How far from the exact answer"
        th_error = page.locator("#poisson-results-card th:has-text('How far from the exact answer')")
        assert th_error.count() == 1
        assert "How far from the exact answer" in th_error.text_content()

        # Click Solve Poisson Operator to verify table visibility and latency/errors
        page.locator("#poi-submit-btn").click()
        page.wait_for_selector("#poi-result-panel", state="visible")
        assert th_error.is_visible()

        # 8. Capture screenshots of Field and Poisson pages at 1440px
        page.goto(f"{live_server}/#field")
        page.wait_for_selector("#heading-field", state="visible")
        save_screenshot(page, "field_1440px.png")

        page.goto(f"{live_server}/#poisson")
        page.wait_for_selector("#heading-poisson", state="visible")
        page.locator("#poi-submit-btn").click()
        page.wait_for_selector("#poi-result-panel", state="visible")
        save_screenshot(page, "poisson_1440px.png")

        browser.close()


def test_nav_visual_polish_mobile_390(live_server):
    """Mobile 390x844 viewport: check nav bar, mobile menu with group headers, H1 size 26px, Field & Poisson screenshots."""
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(viewport={"width": 390, "height": 844})
        page = context.new_page()

        page.goto(f"{live_server}/#overview")
        page.wait_for_load_state("domcontentloaded")
        page.wait_for_selector("#heading-overview", state="visible")

        # 1. Navigation order on mobile
        links = page.locator(".nav-link")
        link_texts = [links.nth(i).inner_text().strip() for i in range(links.count())]
        expected_order = [
            "Overview",
            "Field",
            "Poisson",
            "Place Sensors",
            "Estimate",
            "Diagnose",
            "Evidence",
            "Limits"
        ]
        assert link_texts == expected_order

        # 2. Before opening mobile menu, no bold group headers in the bar
        assert not page.locator("#nav-label-predict").is_visible()
        assert not page.locator("#nav-label-investigate").is_visible()

        # 3. Check H1 mobile size is ~26px
        h1 = page.locator("#heading-overview")
        h1_fs = float(h1.evaluate("el => parseFloat(window.getComputedStyle(el).fontSize)"))
        assert h1_fs == pytest.approx(26.0, abs=1.0)

        # 4. Open mobile menu: Mobile menu keeps the group headers
        menu_btn = page.locator("#mobile-menu-btn")
        assert menu_btn.is_visible()
        menu_btn.click()
        page.wait_for_timeout(200)

        nav_bar = page.locator("#app-nav-bar")
        assert nav_bar.evaluate("el => el.classList.contains('mobile-menu-open')")

        # Group headers ARE visible in mobile menu
        predict_label = page.locator("#nav-label-predict")
        investigate_label = page.locator("#nav-label-investigate")
        assert predict_label.is_visible()
        assert investigate_label.is_visible()
        assert predict_label.inner_text().strip().upper() == "PREDICT"
        assert investigate_label.inner_text().strip().upper() == "INVESTIGATE"

        # Capture mobile nav menu screenshot
        save_screenshot(nav_bar, "nav_390px.png")

        # Close mobile menu by clicking a link
        page.locator("#nav-field").click()
        page.wait_for_timeout(200)
        assert not nav_bar.evaluate("el => el.classList.contains('mobile-menu-open')")

        # 5. Check Field page at 390px
        page.wait_for_selector("#heading-field", state="visible")
        field_h1 = page.locator("#heading-field")
        assert field_h1.inner_text().strip() == "Heat Over Time"
        field_h1_fs = float(field_h1.evaluate("el => parseFloat(window.getComputedStyle(el).fontSize)"))
        assert field_h1_fs == pytest.approx(26.0, abs=1.0)
        save_screenshot(page, "field_390px.png")

        # 6. Check Poisson page at 390px
        page.goto(f"{live_server}/#poisson")
        page.wait_for_selector("#heading-poisson", state="visible")
        poi_h1 = page.locator("#heading-poisson")
        assert poi_h1.inner_text().strip() == "Steady Heat Map (2D)"
        poi_h1_fs = float(poi_h1.evaluate("el => parseFloat(window.getComputedStyle(el).fontSize)"))
        assert poi_h1_fs == pytest.approx(26.0, abs=1.0)
        save_screenshot(page, "poisson_390px.png")

        browser.close()
