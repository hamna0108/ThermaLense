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

        # 1. Desktop 1440x900
        page_desk = browser.new_page(viewport={"width": 1440, "height": 900})
        
        # Navigate to Diagnose
        page_desk.goto(f"{base_url}/#diagnose")
        page_desk.wait_for_selector("#view-diagnose.active", state="visible")
        page_desk.wait_for_timeout(500)

        # Select first demo profile
        page_desk.select_option("#diag-profile-select", index=1)
        page_desk.wait_for_timeout(500)
        
        # Capture Diagnose with Profile
        desk_diag_path = os.path.join(SCREENSHOTS_DIR, "desktop_1440_diagnose_bar_profiles.png")
        page_desk.screenshot(path=desk_diag_path, full_page=True)
        print(f"Captured: {desk_diag_path}")

        # Navigate to Estimate
        page_desk.click("#nav-estimate")
        page_desk.wait_for_selector("#view-estimate.active", state="visible")
        page_desk.wait_for_timeout(500)

        # Capture Estimate with Profile
        desk_est_path = os.path.join(SCREENSHOTS_DIR, "desktop_1440_estimate_bar_profiles.png")
        page_desk.screenshot(path=desk_est_path, full_page=True)
        print(f"Captured: {desk_est_path}")

        page_desk.close()

        # 2. Mobile 390x844
        page_mob = browser.new_page(viewport={"width": 390, "height": 844})
        
        # Navigate to Diagnose
        page_mob.goto(f"{base_url}/#diagnose")
        page_mob.wait_for_selector("#view-diagnose.active", state="visible")
        page_mob.wait_for_timeout(500)

        # Select first demo profile
        page_mob.select_option("#diag-profile-select", index=1)
        page_mob.wait_for_timeout(500)

        mob_diag_path = os.path.join(SCREENSHOTS_DIR, "mobile_390_diagnose_bar_profiles.png")
        page_mob.screenshot(path=mob_diag_path, full_page=True)
        print(f"Captured: {mob_diag_path}")

        # Navigate to Estimate
        page_mob.click("#nav-estimate")
        page_mob.wait_for_selector("#view-estimate.active", state="visible")
        page_mob.wait_for_timeout(500)

        mob_est_path = os.path.join(SCREENSHOTS_DIR, "mobile_390_estimate_bar_profiles.png")
        page_mob.screenshot(path=mob_est_path, full_page=True)
        print(f"Captured: {mob_est_path}")

        page_mob.close()
        browser.close()

    proc.terminate()
    try:
        proc.wait(timeout=3)
    except subprocess.TimeoutExpired:
        proc.kill()
    print("Screenshots captured successfully.")

if __name__ == "__main__":
    main()
