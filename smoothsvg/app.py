"""Desktop app mode: local server on a free port + a pywebview window (browser as fallback)."""
import logging
import os
import socket
import sys
import threading
import webbrowser
from logging.handlers import RotatingFileHandler
from pathlib import Path

TITLE = "smooth-svg"
MUTEX_NAME = "smooth-svg-app"  # the Inno Setup AppMutex must use this same name

# Functions called with the FastAPI app before the server starts (app mode only, never --ui).
SETUP_HOOKS = []
_mutex = None  # single-instance mutex handle, never closed on purpose
_server = None  # the running uvicorn server, set by start_server (used to quit after an update)
_update = {"checked": False, "info": None}  # filled by the background check

log = logging.getLogger("smoothsvg.app")


def log_dir() -> Path:
    base = os.environ.get("LOCALAPPDATA") or str(Path.home() / ".local" / "share")
    return Path(base) / "smooth-svg"


def setup_logging() -> None:
    d = log_dir()
    d.mkdir(parents=True, exist_ok=True)
    h = RotatingFileHandler(d / "app.log", maxBytes=256 * 1024, backupCount=2, encoding="utf-8")
    h.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s"))
    root = logging.getLogger()
    root.addHandler(h)
    root.setLevel(logging.INFO)


def message_box(text: str) -> None:
    """Windows message box; elsewhere (or on failure) only the log."""
    log.error(text)
    try:
        import ctypes
        ctypes.windll.user32.MessageBoxW(None, text, TITLE, 0x10)
    except (AttributeError, OSError):  # not Windows, or the call failed: the log has it
        log.debug("message box unavailable")


def acquire_single_instance():
    """Return a handle to keep alive, or None when another instance already runs."""
    if sys.platform != "win32":
        return True
    import ctypes
    global _mutex
    k32 = ctypes.WinDLL("kernel32", use_last_error=True)
    k32.CreateMutexW.restype = ctypes.c_void_p
    _mutex = k32.CreateMutexW(None, False, MUTEX_NAME)  # kept at module level for the process lifetime
    if ctypes.get_last_error() == 183:  # ERROR_ALREADY_EXISTS
        focus_existing()
        return None
    return _mutex or True


def focus_existing() -> None:
    import ctypes
    u32 = ctypes.windll.user32
    hwnd = u32.FindWindowW(None, TITLE)
    if hwnd:
        u32.ShowWindow(hwnd, 9)  # SW_RESTORE
        u32.SetForegroundWindow(hwnd)


def _update_state() -> dict:
    from . import updater
    s = updater._load(updater.settings_path())
    return {
        "disabled_by_env": bool(os.environ.get("SMOOTHSVG_NO_UPDATE")),
        "check_updates": s.get("check_updates") is not False,
        "checked": _update["checked"],
        "update": _update["info"],
    }


def _background_check() -> None:
    from . import __version__, updater
    _update["info"] = updater.check(__version__)  # never raises
    _update["checked"] = True


def quit_app() -> None:
    """Stop the server and close the window so the installer can replace the files."""
    if _server:
        _server.should_exit = True
    try:
        import webview
        for w in list(webview.windows):
            w.destroy()
    except ImportError:  # no pywebview (browser mode)
        pass


def register_update_routes(app) -> None:
    from typing import Literal

    from fastapi import HTTPException
    from pydantic import BaseModel

    from . import updater

    class Settings(BaseModel):
        check_updates: bool

    class Install(BaseModel):
        confirm: Literal[True]  # a JSON body forces a CORS preflight, so other sites cannot trigger it

    @app.get("/api/update")
    def get_update():
        return _update_state()

    @app.post("/api/update/settings")
    def set_update_settings(body: Settings):
        p = updater.settings_path()
        s = updater._load(p)
        s["check_updates"] = body.check_updates
        updater._save(p, s)
        return _update_state()

    @app.post("/api/update/install")
    def install_update(body: Install):
        info = _update["info"]  # only what our own check found, never a client-supplied URL
        if not info:
            raise HTTPException(404, "no update")
        path = updater.download_and_verify(info["url"], info["sums_url"])
        if path is None:
            raise HTTPException(502, "download failed or hash mismatch")
        if not updater.launch_installer(path):
            raise HTTPException(502, "installer did not start")
        threading.Timer(0.5, quit_app).start()  # after the response is sent
        return {"ok": True}


SETUP_HOOKS.append(register_update_routes)


def start_server():
    import uvicorn

    from .server import app

    for hook in SETUP_HOOKS:
        hook(app)
    sock = socket.socket()
    sock.bind(("127.0.0.1", 0))
    port = sock.getsockname()[1]
    # log_config=None: a windowed exe has no stdout/stderr, uvicorn's default log setup would crash
    server = uvicorn.Server(uvicorn.Config(app, log_config=None))
    global _server
    _server = server
    t = threading.Thread(target=server.run, kwargs={"sockets": [sock]}, daemon=True)
    t.start()
    while not server.started:
        if not t.is_alive():
            raise RuntimeError("server failed to start")
        threading.Event().wait(0.05)
    return server, t, f"http://127.0.0.1:{port}"


def run() -> int:
    setup_logging()
    if acquire_single_instance() is None:
        log.info("another instance is running; focused it")
        return 0
    try:
        server, thread, url = start_server()
    except Exception:
        log.exception("could not start server")
        message_box("smooth-svg could not start. See / Veja %LOCALAPPDATA%\\smooth-svg\\app.log")
        return 1
    log.info("serving %s", url)
    check = threading.Timer(3, _background_check)  # off the UI thread; never blocks opening
    check.daemon = True
    check.start()
    try:
        if os.environ.get("SMOOTHSVG_BROWSER") == "1" or not _open_window(url):
            webbrowser.open(url)
            thread.join()  # browser mode: runs until Ctrl+C or the process is killed
    except KeyboardInterrupt:
        pass
    finally:
        server.should_exit = True
        thread.join(timeout=5)
    return 0


def _open_window(url: str) -> bool:
    """Block until the window closes. False when no window could be shown."""
    try:
        import webview  # only imported in app mode
        webview.settings["ALLOW_DOWNLOADS"] = True  # "Save as" dialog for Download SVG
        webview.create_window(TITLE, url, width=1280, height=860, min_size=(800, 600))
        webview.start()
        return True
    except Exception:
        log.exception("window failed, falling back to the browser")
        message_box("Could not open the window (WebView2 missing?). Opening the browser.\n"
                    "Não foi possível abrir a janela (WebView2 ausente?). Abrindo o navegador.")
        return False
