"""Smoke test: python packaging/smoke.py dist/smooth-svg/smooth-svg.exe
Starts the exe (no update check), finds its port, POSTs /api/convert, closes it. Exit 0 = ok."""
import io
import os
import re
import subprocess
import sys
import time
import urllib.request
import uuid
from pathlib import Path

from PIL import Image


def find_port(pid: int) -> int | None:
    out = subprocess.run(["netstat", "-ano", "-p", "TCP"], capture_output=True, text=True, check=False).stdout
    m = re.search(rf"127\.0\.0\.1:(\d+)\s+0\.0\.0\.0:0\s+LISTENING\s+{pid}\b", out)
    return int(m.group(1)) if m else None


def post_convert(port: int) -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", (64, 64), (200, 30, 30)).save(buf, "PNG")
    b = uuid.uuid4().hex
    body = (f'--{b}\r\nContent-Disposition: form-data; name="file"; filename="t.png"\r\n'
            f"Content-Type: image/png\r\n\r\n").encode() + buf.getvalue() + f"\r\n--{b}--\r\n".encode()
    req = urllib.request.Request(f"http://127.0.0.1:{port}/api/convert", body,
                                 {"Content-Type": f"multipart/form-data; boundary={b}"})
    return urllib.request.urlopen(req, timeout=120).read()


def main(exe: str) -> int:
    env = dict(os.environ, SMOOTHSVG_NO_UPDATE="1")
    env.pop("BROWSER", None)
    p = subprocess.Popen([exe], env=env)
    try:
        port = None
        for _ in range(120):
            if p.poll() is not None:
                print("exe exited early:", p.returncode)
                return 1
            if port := find_port(p.pid):
                break
            time.sleep(0.5)
        if not port:
            print("server did not start")
            return 1
        if urllib.request.urlopen(f"http://127.0.0.1:{port}/", timeout=10).status != 200:
            return 1
        if urllib.request.urlopen(f"http://127.0.0.1:{port}/sample.png", timeout=10).status != 200:  # proves datas
            return 1
        out = post_convert(port)
        if b"<svg" not in out:
            print("no svg in response:", out[:200])
            return 1
        print("ok, port", port, len(out), "bytes")
        return 0
    finally:
        subprocess.run(["taskkill", "/PID", str(p.pid), "/T", "/F"], capture_output=True, check=False)


if __name__ == "__main__":
    sys.exit(main(str(Path(sys.argv[1]).resolve())))




