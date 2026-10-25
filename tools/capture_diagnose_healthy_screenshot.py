import os
import sys
import time
import socket
import subprocess
import threading
from playwright.sync_api import sync_playwright

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCREENSHOTS_DIR = os.path.join(REPO_ROOT, "docs", "ui_screenshots")
os.makedirs(SCREENSHOTS_DIR, exist_ok=True)

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

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 1440, "height": 900})

        # Navigate to Diagnose
        page.goto(f"{base_url}/#diagnose")
        page.wait_for_selector("#view-diagnose.active", state="visible")
        page.wait_for_timeout(500)

        # Click Use Example to populate healthy baseline and test readings
        page.click("#diag-use-example-btn")
        page.wait_for_timeout(400)

        # Click Check my test
        with page.expect_response(lambda r: "/v1/diagnose" in r.url and r.request.method == "POST"):
            page.click("#diag-submit-btn")

        page.wait_for_selector("#diag-result-panel", state="visible")
        page.wait_for_timeout(600)

        out_path = os.path.join(SCREENSHOTS_DIR, "desktop_1440_diagnose_healthy_example_result.png")
        page.screenshot(path=out_path, full_page=True)
        print(f"Captured screenshot to: {out_path}")

        browser.close()

    proc.terminate()
    try:
        proc.wait(timeout=3)
    except subprocess.TimeoutExpired:
        proc.kill()

if __name__ == "__main__":
    main()
