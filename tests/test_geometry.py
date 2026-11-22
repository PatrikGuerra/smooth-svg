import io

import cv2
import numpy as np
from fastapi.testclient import TestClient
from PIL import Image

from smoothsvg.pipeline import convert_array
from smoothsvg.score import score
from smoothsvg.server import app

DARK, RED, WHITE = (2, 55, 48), (200, 40, 40), (255, 255, 255)


def _canvas(size=200):
    img = np.zeros((size, size, 4), np.uint8)  # transparent
    return img


def _svg(img, **kw):
    return convert_array(img, colors=4, smooth=0, **kw)[0]


def test_ring_is_one_evenodd_path_with_a_clear_hole():
    img = _canvas()
    cv2.ellipse(img, (100, 100), (80, 60), 20, 0, 360, (*DARK, 255), -1, cv2.LINE_AA)
    cv2.ellipse(img, (100, 100), (40, 25), 20, 0, 360, (0, 0, 0, 0), -1)
    svg = _svg(img)
    assert 'fill-rule="evenodd"' in svg and "<path" in svg
    assert "a" in svg.split(' d="')[1].split('"')[0]  # arcs, not curve points
    assert score(img, svg)["ssim"] > 0.97
    assert _svg(img, rings=False) != svg


def test_arcs_and_lines_for_a_cut_disc():
    img = _canvas()
    cv2.circle(img, (100, 100), 70, (*RED, 255), -1, cv2.LINE_AA)
    img[:, 100:] = 0  # cut straight: half disc
    svg = _svg(img)
    d = svg.split(' d="')[1].split('"')[0]
    assert "a" in d.lower() and len(d) < 120
    assert score(img, svg)["ssim"] > 0.97


def test_circle_partly_covered_is_still_a_circle():
    img = np.full((200, 200, 4), 255, np.uint8)
    cv2.circle(img, (90, 100), 60, (*RED, 255), -1, cv2.LINE_AA)
    cv2.rectangle(img, (130, 70), (190, 130), (*DARK, 255), -1)  # hides the right part
    svg = _svg(img)
    assert "<circle" in svg or "<ellipse" in svg
    assert score(img, svg)["ssim"] > 0.97
    assert "<circle" not in _svg(img, rings=False) and "<ellipse" not in _svg(img, rings=False)


def _post(rings):
    buf = io.BytesIO()
    Image.fromarray(_canvas()).save(buf, "PNG")
    return TestClient(app).post("/api/convert", files={"file": ("a.png", buf.getvalue())},
                                data={"rings": rings})


def test_server_rejects_bad_rings_value():
    assert _post("maybe").status_code == 400
    assert _post("false").status_code == 200
    assert _post("true").status_code == 200


def test_tiny_circle_is_not_an_arc():
    # v inner notch: a 2 px circle on a sharp tip made a round dot; real arcs still pass
    from smoothsvg.geometry import _arc_ok

    t = np.linspace(0, 1.5 * np.pi, 40)
    ring = lambda r: np.c_[50 + r * np.cos(t), 50 + r * np.sin(t)]
    assert _arc_ok(ring(1.9), 0.8, 500) is None
    assert _arc_ok(ring(30), 0.8, 500) is not None
