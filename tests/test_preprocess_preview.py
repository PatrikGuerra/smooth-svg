import base64
import io
from pathlib import Path

import numpy as np
from fastapi.testclient import TestClient
from PIL import Image

from smoothsvg import server
from smoothsvg.pipeline import load
from smoothsvg.server import _png_url, app
from smoothsvg.smooth import LEVELS

client = TestClient(app)
LOGO = Path(__file__).parent / "samples" / "logo.png"


def _decode(url: str) -> Image.Image:
    assert url.startswith("data:image/png;base64,")
    return Image.open(io.BytesIO(base64.b64decode(url.split(",", 1)[1])))


def _post(**data):
    r = client.post("/api/convert", files={"file": ("l.png", LOGO.read_bytes(), "image/png")},
                    data=data)
    assert r.status_code == 200
    return r.json()


def test_returns_both_stages_with_right_sizes():
    w, h = load(LOGO).shape[1::-1]
    for smooth in (0, 2):
        pre = _post(preset="false", smooth=smooth, colors=5)["pre"]
        k = pre["k"]
        assert 1 <= k <= LEVELS[smooth][0]
        red, up = _decode(pre["reduced"]), _decode(pre["upscaled"])
        assert red.size == (w, h) and up.size == (w * k, h * k) and pre["size"] == [w * k, h * k]
        assert red.mode == up.mode == "P" and not pre["downscaled"]
        assert len(set(np.asarray(red).ravel())) <= 6  # palette + transparent


def test_drawing_model_has_no_preview():
    assert _post(model="drawing")["pre"] is None


def test_big_preview_is_downscaled_nearest(monkeypatch):
    monkeypatch.setattr(server, "MAX_PREVIEW_PX", 100)
    rgba = np.zeros((40, 40, 4), np.uint8)
    rgba[..., :3], rgba[..., 3] = [10, 20, 30], 255
    url, small = _png_url(rgba, np.array([[10, 20, 30]], np.uint8))
    im = _decode(url).convert("RGBA")
    assert small and im.size == (10, 10) and im.getpixel((0, 0)) == (10, 20, 30, 255)
