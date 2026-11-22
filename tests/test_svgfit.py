import io
import math
import re

import numpy as np
from fastapi.testclient import TestClient
from PIL import Image

from smoothsvg.score import render
from smoothsvg.server import app
from smoothsvg.svgfit import fit, parse_path

K = 0.5522847498


def _ellipse_d(cx, cy, rx, ry, rot=0.0, start=0, quarters=4, close=True):
    """Path data of an ellipse (or its first quarters) drawn with cubic Beziers."""
    c, s = math.cos(math.radians(rot)), math.sin(math.radians(rot))

    def tf(x, y):
        return f"{cx + c * x - s * y:.3f} {cy + s * x + c * y:.3f}"

    pts = [((1, 0), (1, K), (K, 1), (0, 1)), ((0, 1), (-K, 1), (-1, K), (-1, 0)),
           ((-1, 0), (-1, -K), (-K, -1), (0, -1)), ((0, -1), (K, -1), (1, -K), (1, 0))]
    d = f"M{tf(rx * pts[start][0][0], ry * pts[start][0][1])}"
    for q in range(quarters):
        _, a, b, e = pts[(start + q) % 4]
        d += "C" + " ".join(tf(rx * x, ry * y) for x, y in (a, b, e))
    return d + ("Z" if close else "")


def _svg(*paths, size=200):
    body = "".join(paths)
    return f'<svg xmlns="http://www.w3.org/2000/svg" width="{size}" height="{size}" viewBox="0 0 {size} {size}">{body}</svg>'


def _p(d, extra=' fill="#c00"'):
    return f'<path d="{d}"{extra}/>'


def test_whole_circle_becomes_circle_element():
    out, st = fit(_svg(_p(_ellipse_d(100, 100, 50, 50))))
    assert "<circle" in out and "<path" not in out and st["circles"] == 1
    m = re.search(r'cx="([\d.]+)" cy="([\d.]+)" r="([\d.]+)"', out)
    assert [round(float(v)) for v in m.groups()] == [100, 100, 50]


def test_tilted_ellipse_keeps_its_rotation():
    svg = _svg(_p(_ellipse_d(100, 100, 70, 30, rot=30)))
    out, st = fit(svg)
    assert "<ellipse" in out and st["ellipses"] == 1 and "rotate(" in out  # may swap axes: 30 deg = 120 deg
    ref = render(svg, 200, 200)
    assert np.abs(render(out, 200, 200).astype(int) - ref).max() < 120  # same picture


def test_partial_arc_in_a_closed_shape():
    d = _ellipse_d(100, 100, 60, 60, quarters=2, close=False) + "L40 100Z"  # half disc
    out, st = fit(_svg(_p(d)))
    assert re.search(r"A60", out) and st["arcs"] == 1
    assert "L40 100" in out  # the straight edge stays


def test_ring_keeps_both_subpaths_and_fill_rule():
    d = _ellipse_d(100, 100, 80, 80) + _ellipse_d(100, 100, 40, 40)
    out, st = fit(_svg(_p(d, ' fill="#c00" fill-rule="evenodd"')))
    assert 'fill-rule="evenodd"' in out and out.count("M") == 2 and out.count("A") == 4
    assert "<circle" not in out and st["arcs"] == 4


def test_straight_and_flat_paths_stay_untouched():
    for d in ("M10 10L190 10L190 190L10 190Z", "M10 100C60 100.5 140 100.5 190 100L190 150Z"):
        svg = _svg(_p(d))
        assert fit(svg)[0] == svg


def test_tolerance_decides():
    svg = _svg(_p(_ellipse_d(100, 100, 50, 50, quarters=3, close=False) + "L100 100Z"))
    assert "A" in fit(svg, tol=0.35)[0]
    assert fit(svg, tol=0.001)[0] == svg  # a Bezier circle is off by ~0.014 px


def test_transform_and_relative_commands():
    d = "m0 0c27.6 0 50 22.4 50 50s-22.4 50-50 50-50-22.4-50-50 22.4-50 50-50z"  # circle r=50
    out, _ = fit(_svg(_p(d, ' fill="#c00" transform="translate(100 100)"')))
    assert "<circle" in out and 'transform="translate(100 100)"' in out
    assert len(parse_path("M0 0 H10 V5 h-10 z")[0]["segs"]) == 4


def test_bad_input_is_returned_as_it_came():
    for s in ("", "not svg", "<svg>", _svg(_p("M10 10 C zzz")), _svg(_p("")),
              _svg(_p("M0 0L1 1", ' transform="skewX(20)"'))):
        assert fit(s)[0] == s


def test_same_input_same_output():
    svg = _svg(_p(_ellipse_d(100, 100, 70, 30, rot=30)), _p(_ellipse_d(60, 60, 20, 20)))
    assert fit(svg)[0] == fit(svg)[0]


def test_render_check_undoes_a_swap_that_hurts(monkeypatch):
    svg = _svg(_p(_ellipse_d(100, 100, 50, 50)))
    ref = render(svg, 200, 200)
    assert "<circle" in fit(svg, ref=ref)[0]  # the exact circle matches the picture: kept
    bad = {"ctr": np.array([100.0, 100.0]), "rx": 40.0, "ry": 40.0, "phi": 0.0}
    monkeypatch.setattr("smoothsvg.svgfit.fit_closed", lambda *a: bad)  # a wrong fit sneaks in
    out, st = fit(svg, ref=ref)
    assert out == svg and st["undone"] == 1
    assert "<circle" in fit(svg)[0]  # without the render check it would have been written


def _post(**data):
    buf = io.BytesIO()
    Image.fromarray(np.zeros((40, 40, 4), np.uint8)).save(buf, "PNG")
    return TestClient(app).post("/api/convert", files={"file": ("a.png", buf.getvalue())}, data=data)


def test_server_validates_geometry_fit():
    assert _post(geometry_fit="maybe").status_code == 400
    assert _post(fit_tol="0.01").status_code == 400
    assert _post(fit_tol="5").status_code == 400
    assert _post(geometry_fit="off").status_code == 200
    assert _post(geometry_fit="auto", fit_tol="0.5").status_code == 200
