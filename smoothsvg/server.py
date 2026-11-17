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

app = FastAPI()
app.mount("/static", StaticFiles(directory=STATIC), name="static")


@app.get("/")
def index():
    return FileResponse(STATIC / "index.html")


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
    )
    stats = score(img, svg, (time.perf_counter() - t) * 1000)
    return {"svg": svg, "stats": stats, "palette": palette, "used": used}
