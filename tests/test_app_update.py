import hashlib
import json
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from smoothsvg import app as appmod
from smoothsvg import updater

OK = {"confirm": True}
INFO = {"version": "9.9.9", "url": updater.ALLOWED_PREFIX + "v9.9.9/x.exe", "sums_url": updater.ALLOWED_PREFIX + "v9.9.9/SHA256SUMS.txt"}


@pytest.fixture
def env(monkeypatch, tmp_path):
    monkeypatch.setenv("APPDATA", str(tmp_path))
    monkeypatch.delenv("SMOOTHSVG_NO_UPDATE", raising=False)
    monkeypatch.setitem(appmod._update, "info", None)
    monkeypatch.setitem(appmod._update, "checked", False)
    quits = []
    monkeypatch.setattr(appmod, "quit_app", lambda: quits.append(1))
    fresh = FastAPI()
    appmod.register_update_routes(fresh)
    return TestClient(fresh), quits


def test_ui_mode_has_no_update_routes():
    from smoothsvg.server import app
    assert not [r for r in app.routes if "/api/update" in getattr(r, "path", "")]
    assert appmod.register_update_routes in appmod.SETUP_HOOKS


def test_state_and_opt_out_setting(env):
    c, _ = env
    assert c.get("/api/update").json() == {"disabled_by_env": False, "check_updates": True, "checked": False, "update": None}
    assert c.post("/api/update/settings", json={"check_updates": False}).json()["check_updates"] is False
    assert json.loads(updater.settings_path().read_text())["check_updates"] is False
    assert c.post("/api/update/settings", json={"check_updates": "maybe"}).status_code == 422


def test_install_without_update_is_404(env):
    c, quits = env
    assert c.post("/api/update/install", json=OK).status_code == 404 and not quits


def test_install_ok_launches_then_quits(env, monkeypatch):
    c, _ = env
    appmod._update["info"] = INFO
    calls = []
    monkeypatch.setattr(updater, "download_and_verify", lambda u, s: calls.append(("dl", u)) or "setup.exe")
    monkeypatch.setattr(updater, "launch_installer", lambda p: calls.append(("run", p)) or True)
    monkeypatch.setattr(appmod.threading, "Timer", lambda s, f: type("T", (), {"start": lambda self: calls.append(("quit",))})())
    assert c.post("/api/update/install", json=OK).json() == {"ok": True}
    assert calls == [("dl", INFO["url"]), ("run", "setup.exe"), ("quit",)]  # D8: quit only after the installer started


@pytest.mark.parametrize("dl,run", [(None, True), ("setup.exe", False)])
def test_install_failure_keeps_app_open(env, monkeypatch, dl, run):
    c, quits = env
    appmod._update["info"] = INFO
    monkeypatch.setattr(updater, "download_and_verify", lambda u, s: dl)
    monkeypatch.setattr(updater, "launch_installer", lambda p: run)
    monkeypatch.setattr(appmod.threading, "Timer", lambda s, f: pytest.fail("must not quit"))
    assert c.post("/api/update/install", json=OK).status_code == 502 and not quits


def test_no_update_env_makes_no_connection(env, monkeypatch):
    monkeypatch.setenv("SMOOTHSVG_NO_UPDATE", "1")
    monkeypatch.setattr(updater, "_get", lambda *_: pytest.fail("network used"))
    appmod._background_check()
    c, _ = env
    s = c.get("/api/update").json()
    assert s["checked"] is True and s["update"] is None and s["disabled_by_env"] is True


def test_end_to_end_with_fake_server(env, monkeypatch, tmp_path):
    c, _ = env
    installer = b"not a real installer"
    files = {
        "/latest": json.dumps({"tag_name": "v9.9.9", "assets": [
            {"name": "smooth-svg-setup-9.9.9.exe", "browser_download_url": "http://127.0.0.1:%d/dl/smooth-svg-setup-9.9.9.exe"},
            {"name": "SHA256SUMS.txt", "browser_download_url": "http://127.0.0.1:%d/dl/SHA256SUMS.txt"}]}).encode(),
        "/dl/smooth-svg-setup-9.9.9.exe": installer,
        "/dl/SHA256SUMS.txt": f"{hashlib.sha256(installer).hexdigest()}  smooth-svg-setup-9.9.9.exe\n".encode(),
    }

    class H(BaseHTTPRequestHandler):
        def do_GET(self):
            body = files.get(self.path)
            self.send_response(200 if body else 404)
            self.end_headers()
            self.wfile.write((body or b"").replace(b"%d", str(self.server.server_port).encode()))

        def log_message(self, *a):
            pass

    srv = HTTPServer(("127.0.0.1", 0), H)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    base = f"http://127.0.0.1:{srv.server_port}"
    monkeypatch.setattr(updater, "API_URL", base + "/latest")
    monkeypatch.setattr(updater, "ALLOWED_PREFIX", base + "/dl/")
    monkeypatch.setattr(updater.tempfile, "gettempdir", lambda: str(tmp_path))
    launched = []
    monkeypatch.setattr(updater, "launch_installer", lambda p: launched.append(p) or True)
    monkeypatch.setattr(appmod.threading, "Timer", lambda s, f: type("T", (), {"start": lambda self: None})())
    try:
        appmod._background_check()
        s = c.get("/api/update").json()
        assert s["checked"] and s["update"]["version"] == "9.9.9"
        assert c.post("/api/update/install", json=OK).json() == {"ok": True}
        assert launched[0].read_bytes() == installer
        files["/dl/SHA256SUMS.txt"] = b"0" * 64 + b"  smooth-svg-setup-9.9.9.exe\n"  # tampered hash
        assert c.post("/api/update/install", json=OK).status_code == 502
    finally:
        srv.shutdown()


@pytest.mark.parametrize("body", [None, {}, {"confirm": False}])
def test_install_requires_confirm_json(env, monkeypatch, body):
    c, quits = env
    appmod._update["info"] = INFO
    monkeypatch.setattr(updater, "download_and_verify", lambda u, s: pytest.fail("must not download"))
    assert c.post("/api/update/install", json=body).status_code == 422 and not quits
    assert c.post("/api/update/install", content=b"").status_code == 422
