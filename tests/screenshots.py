"""Takes the README screenshots of the web page, with the logo in branding/ as the input.

Needs Microsoft Edge or Google Chrome and: pip install -e ".[docs]"
Run:  python tests/screenshots.py
Writes docs/screenshots/*.png
"""
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

from playwright.sync_api import Error as PlaywrightError
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parent.parent
IMAGE = ROOT / "branding" / "Logo+name.png"
OUT = ROOT / "docs" / "screenshots"
PORT = 8766
URL = f"http://127.0.0.1:{PORT}"


def wait_for_server():
    for _ in range(60):
        try:
            urllib.request.urlopen(URL, timeout=1)
            return
        except OSError:
            time.sleep(0.5)
    raise RuntimeError("server did not start")


def zoom(page, x, y, steps):
    page.mouse.move(x, y)
    for _ in range(steps):
        page.mouse.wheel(0, -300)
        page.wait_for_timeout(40)


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    server = subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "smoothsvg.server:app", "--host", "127.0.0.1",
         "--port", str(PORT), "--log-level", "warning"], cwd=ROOT)
    try:
        wait_for_server()
        with sync_playwright() as p:
            try:
                browser = p.chromium.launch(channel="msedge")
            except PlaywrightError:  # no Edge: try Chrome
                browser = p.chromium.launch(channel="chrome")
            page = browser.new_page(viewport={"width": 1600, "height": 900}, device_scale_factor=1)
            page.goto(URL)
            page.set_input_files("#file", str(IMAGE))
            page.wait_for_function(
                "document.getElementById('stats').textContent.includes('SSIM')", timeout=120000)
            page.wait_for_timeout(500)
            page.screenshot(path=str(OUT / "ui-overview.png"))

            # zoom on the cup rim and the leaves: stairs on the left, curves on the right
            zoom(page, 360, 420, 12)
            page.wait_for_timeout(300)
            page.screenshot(path=str(OUT / "ui-zoom.png"))

            page.dblclick("#inPane")  # back to fit
            page.click("#wipeBtn")
            zoom(page, 700, 470, 9)
            page.wait_for_timeout(300)
            page.screenshot(path=str(OUT / "ui-wipe.png"))
            browser.close()
    finally:
        server.terminate()
    print("saved to", OUT)


if __name__ == "__main__":
    main()
