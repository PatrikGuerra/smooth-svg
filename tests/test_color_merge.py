import io
import json
from pathlib import Path

import numpy as np
import pytest
from fastapi.testclient import TestClient
from PIL import Image

from smoothsvg.pipeline import convert_array, load
from smoothsvg.quantize import merge_groups, parse_groups
from smoothsvg.server import app

client = TestClient(app)
LOGO = Path(__file__).parent / "samples" / "logo.png"
BLACK, GRAY, RED, BLUE = "#000000", "#808080", "#FF0000", "#0000FF"
OPTS = {"colors": 4, "merge_de": 5, "smooth": 0, "min_area": 1}  # keep the four blocks apart


def _four_blocks() -> np.ndarray:
    img = np.full((80, 80, 4), 255, np.uint8)
    for i, c in enumerate((BLACK, GRAY, RED, BLUE)):
        img[(i // 2) * 40:(i // 2) * 40 + 40, (i % 2) * 40:(i % 2) * 40 + 40, :3] = [
            int(c[j:j + 2], 16) for j in (1, 3, 5)]
    return img


def _run(groups=()):
    return convert_array(_four_blocks(), groups=parse_groups(json.dumps(groups)) if groups else (),
                         **OPTS)


def test_no_groups_is_identical():
    img = load(LOGO)
    assert convert_array(img) == convert_array(img, groups=parse_groups(""))


def test_merges_only_the_chosen_colors():
    before = dict(_run()[1])
    assert {BLACK, GRAY, RED, BLUE} <= set(before)
    after = dict(_run([{"from": [BLACK, GRAY], "to": BLACK}])[1])
    assert GRAY not in after and {BLACK, RED, BLUE} <= set(after)
    assert len(after) == len(before) - 1
    assert after[BLACK] == pytest.approx(before[BLACK] + before[GRAY])
    assert after[RED] == before[RED]


def test_new_final_color_and_fewer_paths():
    plain, _ = _run()
    svg, pal = _run([{"from": [BLACK, GRAY], "to": "#112233"}])
    names = {c for c, _ in pal}
    assert "#112233" in names and BLACK not in names and GRAY not in names
    assert svg.count("<path") < plain.count("<path")


def test_merge_array_edits_pixels_and_ignores_missing():
    q2, pal = merge_groups(_four_blocks(), [(BLACK, .5), (GRAY, .5)],
                           [([BLACK, GRAY, "#ABCDEF"], GRAY)])
    assert pal == [(GRAY, 1.0)] and not (q2[..., :3] == [0, 0, 0]).all(axis=2).any()


TWO = '{"from":["#000000","#111111"],"to":"#000000"}'


@pytest.mark.parametrize("raw", [
    "nope", "{}", '[{"from":["#000000"],"to":"#000000"}]',
    '[{"from":["#000000","red"],"to":"#000000"}]', '[{"from":["#000000","#111111"],"to":"x"}]',
    '[{"from":["#000000","#111111"]}]', "[1]", "[" + ",".join([TWO] * 17) + "]",
    " " * 5000 + "[]",
])
def test_bad_input_is_rejected(raw):
    with pytest.raises(ValueError):
        parse_groups(raw)
    r = client.post("/api/convert", files={"file": ("l.png", LOGO.read_bytes(), "image/png")},
                    data={"merge_groups": raw})
    assert r.status_code == 400


def test_server_applies_groups():
    files = {"file": ("l.png", LOGO.read_bytes(), "image/png")}
    pal = [c for c, _ in client.post("/api/convert", files=files).json()["palette"]]
    assert len(pal) >= 3
    g = json.dumps([{"from": pal[:2], "to": pal[0]}])
    body = client.post("/api/convert", files=files, data={"merge_groups": g}).json()
    assert len(body["palette"]) == len(pal) - 1 and pal[1] not in dict(body["palette"])
    assert [c for c, _ in body["base"]] == pal  # the panel lists the colors before the groups


def test_drawing_model_ignores_groups():
    buf = io.BytesIO()
    Image.fromarray(_four_blocks()).save(buf, "PNG")
    g = json.dumps([{"from": [BLACK, GRAY], "to": BLACK}])
    r = client.post("/api/convert", files={"file": ("d.png", buf.getvalue(), "image/png")},
                    data={"model": "drawing", "merge_groups": g})
    assert r.status_code == 200


def test_base_palette_is_filled_before_groups():
    base = []
    _, pal = convert_array(_four_blocks(), groups=[([BLACK, GRAY], BLACK)], base=base, **OPTS)
    assert GRAY in dict(base) and GRAY not in dict(pal)
