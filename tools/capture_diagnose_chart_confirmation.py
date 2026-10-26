import os
import sys
import time
import socket
import subprocess
import threading
from playwright.sync_api import sync_playwright

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCREENSHOTS_DIR = os.path.join(REPO_ROOT, "docs", "ui_screenshots")
ARTIFACT_DIR = r"C:\Users\HP\.gemini\antigravity-ide\brain\acb0d46f-cc58-4de4-b39b-b47d6409ab04"
os.makedirs(SCREENSHOTS_DIR, exist_ok=True)
if os.path.exists(ARTIFACT_DIR):
    os.makedirs(ARTIFACT_DIR, exist_ok=True)

def find_free_port():
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(('', 0))
        return s.getsockname()[1]

def wait_for_port(port, timeout=40):
    start = time.time()
    while time.time() - start < timeout:
        try:
            with socket.create_connection(('127.0.0.1', port), timeout=1):
                return True
        except (ConnectionRefusedError, OSError):
            time.sleep(0.5)
    return False

def main():
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

    def drain():
        try:
            for _ in iter(proc.stdout.readline, ''):
                pass
        except Exception:
            pass

    threading.Thread(target=drain, daemon=True).start()
    assert wait_for_port(port, timeout=40), "Server did not start in 40s"

    base_url = f"http://127.0.0.1:{port}"
    print(f"Server started on {base_url}")

    saved_files = []

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)

        for width, height, name in [(1440, 900, "1440px"), (390, 844, "390px")]:
            print(f"\n--- Testing Diagnose Chart at {name} ({width}x{height}) ---")
            page = browser.new_page(viewport={"width": width, "height": height})
            page.goto(f"{base_url}/#diagnose")
            page.wait_for_selector("#view-diagnose.active", state="visible")
            page.wait_for_timeout(400)

            # Use example data: 3 sensor positions (0.03, 0.05, 0.07 m), 10 readings
            page.click("#diag-use-example-btn")
            page.wait_for_timeout(300)

            # Check sensor positions in test readings table
            pos_count = page.locator("#diag-test-table-tbody tr").count()
            print(f"Operational test readings table rows: {pos_count}")

            # Click Check my test
            with page.expect_response(lambda r: "/v1/diagnose" in r.url and r.request.method == "POST"):
                page.click("#diag-submit-btn")

            page.wait_for_selector("#diag-result-panel", state="visible")
            page.wait_for_timeout(500)

            # Verify chart SVG is present
            chart_svg = page.locator("#diag-chart-svg")
            assert chart_svg.is_visible(), "Diagnose chart SVG is not visible"

            # Check text labels inside SVG for overlap
            texts = page.locator("#diag-chart-svg text").all()
            print(f"Total text labels on SVG at {name}: {len(texts)}")
            text_data = []
            for t in texts:
                box = t.bounding_box()
                content = t.text_content().strip()
                if box and content:
                    text_data.append((content, box))
                    print(f"  Label: '{content}' at x={box['x']:.1f}, y={box['y']:.1f}, w={box['width']:.1f}, h={box['height']:.1f}")

            # Collision check: no two text bounding boxes should overlap by more than 3px in both axes
            overlaps = []
            for i in range(len(text_data)):
                for j in range(i + 1, len(text_data)):
                    c1, b1 = text_data[i]
                    c2, b2 = text_data[j]
                    overlap_x = max(0, min(b1['x'] + b1['width'], b2['x'] + b2['width']) - max(b1['x'], b2['x']))
                    overlap_y = max(0, min(b1['y'] + b1['height'], b2['y'] + b2['height']) - max(b1['y'], b2['y']))
                    if overlap_x > 3 and overlap_y > 3:
                        overlaps.append((c1, c2, overlap_x, overlap_y))

            print(f"Detected label collisions at {name}: {len(overlaps)}")
            for o in overlaps:
                print(f"  COLLISION: '{o[0]}' and '{o[1]}' overlap by {o[2]:.1f}x{o[3]:.1f}px")

            assert len(overlaps) == 0, f"Found {len(overlaps)} overlapping labels on chart at {name}!"

            # Take screenshot of chart card
            chart_card = page.locator("#diagnose-results-card")
            card_filename = f"diagnose_chart_{name}.png"
            card_path = os.path.join(SCREENSHOTS_DIR, card_filename)
            chart_card.screenshot(path=card_path)
            saved_files.append(card_path)

            # Also copy to artifacts dir
            if os.path.exists(ARTIFACT_DIR):
                art_card = os.path.join(ARTIFACT_DIR, card_filename)
                chart_card.screenshot(path=art_card)
                saved_files.append(art_card)

            # Full page screenshot
            full_filename = f"diagnose_full_{name}.png"
            full_path = os.path.join(SCREENSHOTS_DIR, full_filename)
            page.screenshot(path=full_path, full_page=True)
            saved_files.append(full_path)
            if os.path.exists(ARTIFACT_DIR):
                art_full = os.path.join(ARTIFACT_DIR, full_filename)
                page.screenshot(path=art_full, full_page=True)
                saved_files.append(art_full)

            page.close()

        browser.close()

    proc.terminate()
    print("\nConfirmation complete! Generated screenshot files:")
    for f in set(saved_files):
        print(f" - {f}")

if __name__ == "__main__":
    main()
