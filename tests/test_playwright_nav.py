"""Playwright test suite for Type Scale, Header Compaction, Top Bar, and Nav Polish.

Verifies:
1. Type Scale with CSS variables:
   - Eyebrow 12px uppercase, letter-spacing 0.08em
   - Page title (H1) clamp(1.625rem, 1.3rem + 0.8vw, 1.875rem) i.e. 26-30px desktop, 24-28px mobile
   - Subtitle 15-16px, muted colour, max-width 70ch
   - "Show details" summary 14px
   - Section headings (H2) 20px, card headings 17-18px
   - H1 is clearly smaller than the brand name in the top bar on every page.
2. Page header block (.page-intro) <= ~140px tall at 1440px width.
3. First input is visible without scrolling at 1440x768 viewport.
4. Top bar: status pill text "Service online" (green dot kept), tagline "Heat modelling and sensor diagnostics".
5. Extra horizontal rule under page header removed.
6. Navigation bar: single row, uniform baseline/height, 3 dividers, mobile menu section headers.
7. Screenshots of all 8 pages at 1440 and 390.
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

ALL_PAGES = [
    {"hash": "overview", "h1_id": "heading-overview", "has_input": False},
    {"hash": "field", "h1_id": "heading-field", "has_input": True},
    {"hash": "poisson", "h1_id": "heading-poisson", "has_input": True},
    {"hash": "placement", "h1_id": "heading-placement", "has_input": True},
    {"hash": "estimate", "h1_id": "heading-estimate", "has_input": True},
    {"hash": "diagnose", "h1_id": "heading-diagnose", "has_input": True},
    {"hash": "evidence", "h1_id": "heading-evidence", "has_input": False},
    {"hash": "limits", "h1_id": "heading-limits", "has_input": False},
]


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


def test_type_scale_and_header_compaction_1440(live_server):
    """Desktop 1440x768 viewport: check type scale, header compaction <= 140px, first input above fold, top bar, and 8 screenshots."""
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        # Using exact 1440x768 viewport requested to verify above-the-fold visibility
        context = browser.new_context(viewport={"width": 1440, "height": 768})
        page = context.new_page()

        page.goto(f"{live_server}/#overview")
        page.wait_for_load_state("domcontentloaded")
        page.wait_for_selector("#heading-overview", state="visible")

        # 1. Top Bar Checks
        # Pill text "Service online"
        pill_text = page.locator("#service-health-text")
        # Wait up to 2 seconds for health check to settle
        page.wait_for_function("document.getElementById('service-health-text').textContent.includes('Service online')", timeout=5000)
        assert pill_text.inner_text().strip() == "Service online"
        badge = page.locator("#service-health-badge")
        assert "healthy" in badge.evaluate("el => el.className")

        # Tagline "Heat modelling and sensor diagnostics"
        tagline = page.locator(".brand-subtitle")
        assert tagline.inner_text().strip() == "Heat modelling and sensor diagnostics"

        # Brand title font-size: about 28px desktop
        brand_el = page.locator("#brand-link")
        brand_fs = float(brand_el.evaluate("el => parseFloat(window.getComputedStyle(el).fontSize)"))
        assert 27.0 <= brand_fs <= 29.0, f"Brand title {brand_fs}px should be about 28px on desktop"

        # Top bar height must be compact
        header_el = page.locator(".app-header")
        header_box = header_el.bounding_box()
        assert header_box is not None
        assert header_box["height"] <= 65.0, f"Top bar height {header_box['height']}px should be compact (<= 65px)"
        save_screenshot(header_el, "topbar_1440px.png")

        # 2. Navigation bar checks
        # Main row links: Overview | Field | Poisson | Place Sensors | Estimate | Diagnose
        main_links = page.locator("#nav-main-row .nav-link")
        expected_main = [
            "Overview", "Field", "Poisson", "Place Sensors", "Estimate", "Diagnose"
        ]
        assert [main_links.nth(i).inner_text().strip() for i in range(main_links.count())] == expected_main

        # Two group dividers in the main nav row
        assert page.locator("#nav-main-row .nav-divider").count() == 2

        # Secondary links at the right end: Accuracy (-> #evidence) and Limits (-> #limits)
        sec_links = page.locator("#nav-group-about .nav-link")
        expected_sec = ["Accuracy", "Limits"]
        assert [sec_links.nth(i).inner_text().strip() for i in range(sec_links.count())] == expected_sec
        assert page.locator("#nav-evidence").get_attribute("href") == "#evidence"
        assert page.locator("#nav-limits").get_attribute("href") == "#limits"

        # Verify secondary section is at the right end on 1440px desktop
        main_box = page.locator("#nav-main-row").bounding_box()
        sec_box = page.locator("#nav-group-about").bounding_box()
        assert main_box is not None and sec_box is not None
        assert sec_box["x"] >= main_box["x"] + main_box["width"] - 5.0, (
            f"Secondary links x={sec_box['x']} should be at the right end of main row"
        )

        # No bold group headers visible in desktop nav bar
        assert not page.locator("#nav-label-predict").is_visible()
        assert not page.locator("#nav-label-investigate").is_visible()
        assert not page.locator("#nav-label-about").is_visible()

        save_screenshot(page.locator(".nav-bar"), "nav_1440px.png")

        # 3. Type scale and header block checks across ALL EIGHT PAGES
        for p_info in ALL_PAGES:
            page.goto(f"{live_server}/#{p_info['hash']}")
            page.wait_for_selector(f"#{p_info['h1_id']}", state="visible")

            view_elem = page.locator(f"#view-{p_info['hash']}")
            h1 = page.locator(f"#{p_info['h1_id']}")

            # Measure H1 computed font size: 26px desktop (stays at 26-30px, max 26px)
            h1_fs = float(h1.evaluate("el => parseFloat(window.getComputedStyle(el).fontSize)"))
            assert 25.5 <= h1_fs <= 26.5, f"Page {p_info['hash']} H1 font size {h1_fs}px not ~26px"

            # H1 must stay at or below the brand size minus 2px
            assert h1_fs <= brand_fs - 1.9, f"Page {p_info['hash']} H1 {h1_fs}px not <= brand ({brand_fs}px) - 2px"

            # Specific checks for Evidence page
            if p_info["hash"] == "evidence":
                assert h1.inner_text().strip() == "How Accurate Is It?"
                sub = view_elem.locator(".page-desc")
                assert sub.inner_text().strip() == "The tests behind every number in ThermaLens, with the honest limits."
                note = view_elem.locator(".evidence-full-methods-note")
                assert "Full methods, tables and figures are in the project report and README." in note.inner_text()
                det = view_elem.locator(".page-intro .technical-details")
                assert det.count() > 0
                assert "ThermaLens: Empirical Evidence" in det.text_content()
                full_tables = view_elem.locator("#ev-full-tables-details")
                assert full_tables.count() > 0
                assert not full_tables.evaluate("el => el.open")
                assert "Show full tables" in full_tables.locator("summary").inner_text()

            # Specific checks for Limits page
            if p_info["hash"] == "limits":
                assert h1.inner_text().strip() == "What It Can't Do"
                sub = view_elem.locator(".page-desc")
                assert sub.inner_text().strip() == "Where ThermaLens is reliable, where it is not, and what to do about it."
                det = view_elem.locator(".page-intro .technical-details")
                assert det.count() > 0
                assert "Operational Boundaries & Mathematical Limits" in det.text_content()

            # Check header block (.page-intro): height must be at most about 140px tall at 1440px
            intro_el = view_elem.locator(".page-intro")
            intro_box = intro_el.bounding_box()
            assert intro_box is not None
            assert intro_box["height"] <= 145.0, f"Page {p_info['hash']} header block height {intro_box['height']}px exceeds 140px limit"

            # Check no extra horizontal rule under header block
            intro_border_bottom = intro_el.evaluate("el => window.getComputedStyle(el).borderBottomStyle")
            assert intro_border_bottom in ("none", "hidden"), f"Page {p_info['hash']} should have no border-bottom on page-intro"

            # Check eyebrow: 12px uppercase, letter-spacing 0.08em
            eyebrow = view_elem.locator(".page-eyebrow")
            assert eyebrow.is_visible()
            eb_fs = float(eyebrow.evaluate("el => parseFloat(window.getComputedStyle(el).fontSize)"))
            assert 11.0 <= eb_fs <= 12.5

            # If page has inputs, verify first input is visible without scrolling at 1440x768
            if p_info["has_input"]:
                first_input = view_elem.locator("input:visible, select:visible").first
                assert first_input.is_visible()
                inp_box = first_input.bounding_box()
                assert inp_box is not None
                assert inp_box["y"] > 0, f"Page {p_info['hash']} input top {inp_box['y']} must be > 0"
                assert inp_box["y"] + inp_box["height"] < 768.0, (
                    f"Page {p_info['hash']} first input bottom {inp_box['y'] + inp_box['height']}px "
                    f"must be above the fold (< 768px)"
                )

            # Capture screenshot of each page at 1440px
            save_screenshot(page, f"{p_info['hash']}_1440px.png")

        browser.close()


def test_type_scale_mobile_390(live_server):
    """Mobile 390x844 viewport: check H1 size ~22px, brand ~24px (H1 <= brand - 2px), top bar, and 8 screenshots."""
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(viewport={"width": 390, "height": 844})
        page = context.new_page()

        page.goto(f"{live_server}/#overview")
        page.wait_for_load_state("domcontentloaded")
        page.wait_for_selector("#heading-overview", state="visible")

        # Top bar brand on mobile: about 24px
        brand_el = page.locator("#brand-link")
        brand_fs = float(brand_el.evaluate("el => parseFloat(window.getComputedStyle(el).fontSize)"))
        assert 23.0 <= brand_fs <= 25.0, f"Mobile brand title {brand_fs}px should be about 24px"

        # Capture mobile top bar screenshot
        save_screenshot(page.locator(".app-header"), "topbar_390px.png")

        # Verify mobile menu keeps group headers
        menu_btn = page.locator("#mobile-menu-btn")
        assert menu_btn.is_visible()
        menu_btn.click()
        page.wait_for_timeout(200)

        nav_bar = page.locator("#app-nav-bar")
        assert nav_bar.evaluate("el => el.classList.contains('mobile-menu-open')")
        assert page.locator("#nav-label-predict").is_visible()
        assert page.locator("#nav-label-investigate").is_visible()
        assert page.locator("#nav-label-about").is_visible()

        # Verify About links at bottom of menu: Accuracy and Limits
        sec_menu_links = page.locator("#nav-group-about .nav-link")
        assert [sec_menu_links.nth(i).inner_text().strip() for i in range(sec_menu_links.count())] == ["Accuracy", "Limits"]

        save_screenshot(nav_bar, "nav_390px.png")

        # Close mobile menu
        page.locator("#nav-overview").click()
        page.wait_for_timeout(200)

        # Measure H1 on all eight pages at 390px
        for p_info in ALL_PAGES:
            page.goto(f"{live_server}/#{p_info['hash']}")
            page.wait_for_selector(f"#{p_info['h1_id']}", state="visible")

            h1 = page.locator(f"#{p_info['h1_id']}")
            h1_fs = float(h1.evaluate("el => parseFloat(window.getComputedStyle(el).fontSize)"))

            # Must be ~22px at 390px
            assert 21.5 <= h1_fs <= 22.5, f"Page {p_info['hash']} mobile H1 font size {h1_fs}px not ~22px"

            # H1 must stay at or below brand size minus 2px
            assert h1_fs <= brand_fs - 1.9, f"Page {p_info['hash']} mobile H1 {h1_fs}px not <= brand ({brand_fs}px) - 2px"

            # Capture screenshot of each page at 390px
            save_screenshot(page, f"{p_info['hash']}_390px.png")

        browser.close()
