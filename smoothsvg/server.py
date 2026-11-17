import time
from pathlib import Path

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from .pipeline import load_bytes, trace
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
    filter_speckle: int = Form(4),
    color_precision: int = Form(6),
    corner_threshold: int = Form(60),
):
    data = await file.read(MAX_BYTES + 1)
    if len(data) > MAX_BYTES:
        raise HTTPException(413, "file over 20 MB")
    try:
        img = load_bytes(data)
    except Exception as e:  # PIL raises many types for bad files
        raise HTTPException(400, str(e)) from e
    t = time.perf_counter()
    svg = trace(
        img,
        filter_speckle=filter_speckle,
        color_precision=color_precision,
        corner_threshold=corner_threshold,
    )
    return {"svg": svg, "stats": score(img, svg, (time.perf_counter() - t) * 1000)}
