"""Playwright test suite for Top Navigation Reordering, Group Labels, and Page Subtitles.

Verifies:
1. Nav order: Overview | Field | Poisson | Place Sensors | Estimate | Diagnose | Evidence | Limits.
2. Plain words group labels:
   - "Predict" over Field and Poisson.
   - "Investigate" over Place Sensors, Estimate, and Diagnose.
   - On mobile, labels appear as section headers in the menu.
3. Subtitles under page titles:
   - Field and Poisson: "Predict: if we know the material or source, what will the temperature be?"
   - Place Sensors, Estimate, and Diagnose: "Investigate: start from measurements and work backwards."
4. Verified at both 1440 px (desktop) and 390 px (mobile).
5. Captures screenshot of nav at both viewport sizes.
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


def save_screenshot(element, filename):
    filepath = os.path.join(SCREENSHOTS_DIR, filename)
    element.screenshot(path=filepath)
    if os.path.isdir(ARTIFACT_DIR):
        try:
            shutil.copy2(filepath, os.path.join(ARTIFACT_DIR, filename))
        except Exception:
            pass


def test_nav_order_group_labels_and_subtitles_1440(live_server):
    """Desktop 1440x900 viewport: check nav order, Predict & Investigate labels, and page subtitles."""
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(viewport={"width": 1440, "height": 900})
        page = context.new_page()

        page.goto(f"{live_server}/#overview")
        page.wait_for_load_state("networkidle")

        # 1. Check exact nav link order
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

        # 2. Check group labels are present and visible above nav items
        predict_label = page.locator("#nav-label-predict")
        investigate_label = page.locator("#nav-label-investigate")
        assert predict_label.is_visible()
        assert investigate_label.is_visible()
        assert predict_label.inner_text().strip() == "Predict"
        assert investigate_label.inner_text().strip() == "Investigate"

        # Check links inside groups
        predict_links = page.locator("#nav-group-predict .nav-link")
        assert [predict_links.nth(i).inner_text().strip() for i in range(predict_links.count())] == ["Field", "Poisson"]

        investigate_links = page.locator("#nav-group-investigate .nav-link")
        assert [investigate_links.nth(i).inner_text().strip() for i in range(investigate_links.count())] == ["Place Sensors", "Estimate", "Diagnose"]

        # 3. Check subtitles under page titles
        # Field
        page.goto(f"{live_server}/#field")
        page.wait_for_selector("#field-page-subtitle", state="visible")
        assert page.locator("#field-page-subtitle").inner_text().strip() == "Predict: if we know the material or source, what will the temperature be?"

        # Poisson
        page.goto(f"{live_server}/#poisson")
        page.wait_for_selector("#poisson-page-subtitle", state="visible")
        assert page.locator("#poisson-page-subtitle").inner_text().strip() == "Predict: if we know the material or source, what will the temperature be?"

        # Place Sensors
        page.goto(f"{live_server}/#placement")
        page.wait_for_selector("#placement-page-subtitle", state="visible")
        assert page.locator("#placement-page-subtitle").inner_text().strip() == "Investigate: start from measurements and work backwards."

        # Estimate
        page.goto(f"{live_server}/#estimate")
        page.wait_for_selector("#estimate-page-subtitle", state="visible")
        assert page.locator("#estimate-page-subtitle").inner_text().strip() == "Investigate: start from measurements and work backwards."

        # Diagnose
        page.goto(f"{live_server}/#diagnose")
        page.wait_for_selector("#diagnose-page-subtitle", state="visible")
        assert page.locator("#diagnose-page-subtitle").inner_text().strip() == "Investigate: start from measurements and work backwards."

        # 4. Capture screenshot of nav-bar and full top header at 1440px
        save_screenshot(page.locator(".nav-bar"), "nav_1440px.png")
        full_clip_path = os.path.join(SCREENSHOTS_DIR, "nav_field_page_1440px.png")
        page.screenshot(path=full_clip_path, clip={"x": 0, "y": 0, "width": 1440, "height": 260})
        if os.path.isdir(ARTIFACT_DIR):
            try:
                shutil.copy2(full_clip_path, os.path.join(ARTIFACT_DIR, "nav_field_page_1440px.png"))
            except Exception:
                pass

        browser.close()


def test_nav_order_group_labels_and_mobile_menu_390(live_server):
    """Mobile 390x844 viewport: check nav order, section headers, and mobile menu."""
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(viewport={"width": 390, "height": 844})
        page = context.new_page()

        page.goto(f"{live_server}/#overview")
        page.wait_for_load_state("networkidle")

        # 1. Check exact nav link order
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

        # 2. Check group labels are present and visible as section headers on mobile
        predict_label = page.locator("#nav-label-predict")
        investigate_label = page.locator("#nav-label-investigate")
        assert predict_label.is_visible()
        assert investigate_label.is_visible()
        assert predict_label.inner_text().strip() == "Predict"
        assert investigate_label.inner_text().strip() == "Investigate"

        # 3. Test mobile menu toggle button expands vertical menu with section headers
        menu_btn = page.locator("#mobile-menu-btn")
        assert menu_btn.is_visible()
        menu_btn.click()
        page.wait_for_timeout(200)

        nav_bar = page.locator("#app-nav-bar")
        assert nav_bar.evaluate("el => el.classList.contains('mobile-menu-open')")

        # In expanded mobile menu, verify section headers and all links remain visible and accessible
        assert predict_label.is_visible()
        assert investigate_label.is_visible()
        assert page.locator("#nav-field").is_visible()
        assert page.locator("#nav-poisson").is_visible()
        assert page.locator("#nav-placement").is_visible()
        assert page.locator("#nav-estimate").is_visible()
        assert page.locator("#nav-diagnose").is_visible()

        # Capture screenshot of mobile nav menu
        save_screenshot(nav_bar, "nav_390px.png")
        full_clip_390 = os.path.join(SCREENSHOTS_DIR, "nav_menu_full_390px.png")
        page.screenshot(path=full_clip_390, clip={"x": 0, "y": 0, "width": 390, "height": 450})
        if os.path.isdir(ARTIFACT_DIR):
            try:
                shutil.copy2(full_clip_390, os.path.join(ARTIFACT_DIR, "nav_menu_full_390px.png"))
            except Exception:
                pass

        # Clicking a link closes the menu
        page.locator("#nav-field").click()
        page.wait_for_timeout(200)
        assert not nav_bar.evaluate("el => el.classList.contains('mobile-menu-open')")
        assert "#field" in page.url

        browser.close()
