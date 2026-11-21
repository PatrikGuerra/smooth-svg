# PyInstaller spec: pyinstaller packaging/smooth-svg.spec --noconfirm  (run make_ico.py first)
from pathlib import Path

from PyInstaller.utils.hooks import collect_all, collect_submodules

ROOT = Path(SPECPATH).parent

datas = [(str(ROOT / "smoothsvg" / "static"), "smoothsvg/static"),
         (str(ROOT / "branding" / "Logo+name.png"), "branding")]
binaries, hiddenimports = [], collect_submodules("uvicorn") + ["webview.platforms.edgechromium"]
for pkg in ("resvg_py", "vtracer", "potrace", "cv2", "webview"):
    d, b, h = collect_all(pkg)
    datas += d
    binaries += b
    hiddenimports += h

a = Analysis(
    [str(ROOT / "packaging" / "smooth_svg_app.py")],
    pathex=[str(ROOT)],
    datas=datas, binaries=binaries, hiddenimports=hiddenimports,
    excludes=["tkinter", "matplotlib", "IPython", "pytest", "playwright", "PyQt5", "PyQt6",
              "PySide2", "PySide6", "skimage", "scipy", "networkx", "imageio", "pandas"],
)
# videoio ffmpeg (41 MB) is only loaded by cv2.VideoCapture, which the project never uses.
a.binaries = [b for b in a.binaries if "opencv_videoio_ffmpeg" not in b[0]]
pyz = PYZ(a.pure)
exe = EXE(pyz, a.scripts, [], exclude_binaries=True, name="smooth-svg", console=False,
          icon=str(ROOT / "packaging" / "smooth-svg.ico"), upx=False)
coll = COLLECT(exe, a.binaries, a.datas, name="smooth-svg", upx=False)

