import io
from pathlib import Path

from fastapi.testclient import TestClient

from smoothsvg.server import app

client = TestClient(app)
LOGO = Path(__file__).parent / "samples" / "logo.png"


def test_convert_ok():
    r = client.post("/api/convert", files={"file": ("logo.png", LOGO.read_bytes(), "image/png")})
    assert r.status_code == 200
    body = r.json()
    assert body["svg"].startswith("<svg") and body["stats"]["ssim"] > 0.9


def test_convert_bad_file():
    r = client.post("/api/convert", files={"file": ("x.png", io.BytesIO(b"nope"), "image/png")})
    assert r.status_code == 400
