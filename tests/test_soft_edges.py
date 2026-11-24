import io

import numpy as np
from fastapi.testclient import TestClient
from PIL import Image

from smoothsvg import smooth
from smoothsvg.server import app

client = TestClient(app)
RED, WHITE = np.array([200, 30, 30], np.uint8), np.array([255, 255, 255], np.uint8)


def _fade():
    """Red | pink fade | white, rows repeated; q is the same with the fade cut flat."""
    img = np.zeros((6, 12, 4), np.uint8)
    img[..., 3] = 255
    img[:, :4, :3], img[:, 8:, :3] = RED, WHITE
    for x in range(4, 8):
        img[:, x, :3] = (RED + (WHITE.astype(int) - RED) * (x - 3) / 5).astype(np.uint8)
    q = img.copy()
    q[:, 4:6, :3], q[:, 6:8, :3] = RED, WHITE
    return img, q, np.array([RED, WHITE])


def test_soft_edges_never_blend_colors():
    img, q, pal = _fade()
    out, k = smooth.upscale(q, pal, 2, src=img)
    assert k == 3
    colors = {tuple(c) for c in out.reshape(-1, 4)[:, :3]}
    assert colors == {tuple(RED), tuple(WHITE)}  # no pink
    row = (out[3, :, :3] == WHITE).all(axis=1)  # red first, then white, cut inside the fade
    assert 4 * k < row.argmax() < 8 * k and row[row.argmax():].all()


def test_soft_alpha_edge_is_soft():
    img, q, pal = _fade()
    img[:, :, 3] = np.linspace(255, 0, 12).astype(np.uint8)  # alpha fades out to the right
    out, _ = smooth.upscale(q, pal, 2, src=img)
    opaque = out[3, :, 3] == 255
    assert opaque[0] and not opaque[-1] and set(out[..., 3].ravel()) <= {0, 255}


def test_cap_follows_free_memory(monkeypatch):
    _, q, pal = _fade()
    monkeypatch.setattr(smooth, "max_work_px", lambda: 6 * 12)  # room for k=1 only
    assert smooth.upscale(q, pal, 2)[1] == 1
    monkeypatch.setattr(smooth, "max_work_px", lambda: 10**9)
    assert smooth.upscale(q, pal, 2)[1] == 3  # no fixed 2.5 MP cap any more
    monkeypatch.undo()
    monkeypatch.setattr(smooth.psutil, "virtual_memory", lambda: type("M", (), {"available": 10**9}))
    assert smooth.max_work_px() == int(10**9 * smooth.FREE_SHARE / smooth.BYTES_PER_PX)


def _png():
    img = np.zeros((20, 20, 4), np.uint8)
    img[..., 3] = 255
    img[:, 10:, :3] = 255
    buf = io.BytesIO()
    Image.fromarray(img).save(buf, "PNG")
    return buf.getvalue()


def test_api_soft_edges_param():
    def post(**d):
        return client.post("/api/convert", files={"file": ("a.png", _png(), "image/png")}, data=d)

    for v in ("true", "false"):
        assert post(soft_edges=v).status_code == 200
    assert post().status_code == 200  # default is on
    assert post(soft_edges="maybe").status_code == 400
