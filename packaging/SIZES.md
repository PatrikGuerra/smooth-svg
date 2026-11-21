# Sizes (measured 2026-11-20, Windows 11, Python 3.12, PyInstaller --onedir, no UPX)

| Item | MB |
|---|---|
| dist\smooth-svg folder (257 files) | 163.2 |
| smooth-svg.zip (Compress-Archive) | 64.4 |
| smooth-svg-setup-0.2.0.exe (Inno, lzma2 solid) | 45.7 |

Biggest part: cv2 (~85 MB after dropping `opencv_videoio_ffmpeg`, which saved 39 MB of folder and ~16 MB of zip). Before that drop: folder 202.4, zip 80.4.
Installer is under the plan limit of ~80 MB.
