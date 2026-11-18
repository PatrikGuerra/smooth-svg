import re
import time
from pathlib import Path

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from .pipeline import convert_image, load_bytes
from .presets import MODELS
from .score import score

MAX_BYTES = 20 * 1024 * 1024
STATIC = Path(__file__).parent / "static"
SAMPLE = Path(__file__).parent.parent / "branding" / "Logo+name.png"  # only in a repo checkout

app = FastAPI()
app.mount("/static", StaticFiles(directory=STATIC), name="static")


@app.get("/")
def index():
    return FileResponse(STATIC / "index.html")


@app.api_route("/sample.png", methods=["GET", "HEAD"])
def sample():
    if not SAMPLE.is_file():
        raise HTTPException(404, "no sample image")
    return FileResponse(SAMPLE, media_type="image/png")


@app.post("/api/convert")
async def convert(
    file: UploadFile = File(...),
    model: str = Form("auto"),
    preset: bool = Form(True),
    filter_speckle: int = Form(1),
    colors: int = Form(0),
    disabled: str = Form(""),
    smooth: int = Form(2),
    remove_bg: bool = Form(False),
    min_area: int = Form(0),
    merge_de: float = Form(10.0),
    corner: int = Form(0),
    detail: int = Form(0),
    denoise: bool = Form(True),
    ellipses: bool = Form(True),
    polygons: bool = Form(False),
    shape_tol: float = Form(3.0),
):
    data = await file.read(MAX_BYTES + 1)
    if len(data) > MAX_BYTES:
        raise HTTPException(413, "file over 20 MB")
    try:
        img = load_bytes(data)
    except Exception as e:  # PIL raises many types for bad files
        raise HTTPException(400, str(e)) from e
    if model not in MODELS or not 0 <= smooth <= 5:
        raise HTTPException(400, f"model must be one of {MODELS}, smooth 0-5")
    if not (0 <= merge_de <= 60 and 0 <= corner <= 180 and 0 <= detail <= 20 and min_area >= 0
            and 0.5 <= shape_tol <= 20):
        raise HTTPException(
            400, "merge_de 0-60, corner 0-180, detail 0-20, min_area >= 0, shape_tol 0.5-20")
    t = time.perf_counter()
    svg, palette, used = convert_image(
        img,
        model,
        colors=None if preset else colors,
        smooth=None if preset else smooth,
        disabled=set(re.findall(r"#[0-9A-Fa-f]{6}", disabled)),
        filter_speckle=filter_speckle,
        remove_bg=remove_bg,
        min_area=min_area or None,
        merge_de=merge_de,
        corner=corner or None,
        detail=detail or None,
        clean=denoise,
        ellipses=ellipses,
        polygons=polygons,
        shape_tol=shape_tol,
    )
    stats = score(img, svg, (time.perf_counter() - t) * 1000)
    return {"svg": svg, "stats": stats, "palette": palette, "used": used}
