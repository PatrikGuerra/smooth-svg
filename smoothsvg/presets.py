# Model -> defaults. None means "decide from the image". Explicit arguments always win.
PRESETS = {
    "drawing": {"colors": 2, "smooth": 3, "tracer": "potrace"},
    "clipart": {"colors": None, "smooth": 2, "tracer": "vtracer"},
    "pixelart": {"colors": None, "smooth": 3, "min_area": 1, "tracer": "vtracer"},
    "photo": {"colors": 8, "smooth": 1, "tracer": "vtracer"},
}
MODELS = ("auto", *PRESETS)
