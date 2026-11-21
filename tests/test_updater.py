import hashlib
import io
import json

import pytest

from smoothsvg import updater as u

P = u.ALLOWED_PREFIX


def test_versions():
    assert u.parse_version("v1.2.3") == (1, 2, 3)
    assert u.parse_version("1.2") is None and u.parse_version("v1.2.3-rc1") is None
    assert u.is_newer("0.2.0", "0.1.0") and u.is_newer("0.10.0", "0.9.0")
    assert not u.is_newer("0.1.0", "0.1.0") and not u.is_newer("junk", "0.1.0")


def release(tag="v0.2.0", **kw):
    v = tag[1:]
    return {"tag_name": tag, "assets": [
        {"name": f"smooth-svg-setup-{v}.exe", "browser_download_url": f"{P}{tag}/smooth-svg-setup-{v}.exe"},
        {"name": "SHA256SUMS.txt", "browser_download_url": f"{P}{tag}/SHA256SUMS.txt"}], **kw}


@pytest.fixture
def env(tmp_path, monkeypatch):
    monkeypatch.delenv("SMOOTHSVG_NO_UPDATE", raising=False)
    calls = []

    def fake(url):
        calls.append(url)
        return json.dumps(fake.data).encode()

    fake.data = release()
    monkeypatch.setattr(u, "_get", fake)
    return tmp_path / "settings.json", calls, fake


def test_check_finds_update_and_caches(env):
    path, calls, _ = env
    r = u.check("0.1.0", path)
    assert r["version"] == "0.2.0"
    assert u.check("0.1.0", path) == r and len(calls) == 1  # 24h cache


@pytest.mark.parametrize("data", [release(draft=True), release(prerelease=True), release("v0.2.0-rc1"), release("v0.1.0"),
                                  {"tag_name": "v0.2.0", "assets": [{"name": "smooth-svg-setup-0.2.0.exe", "browser_download_url": "https://evil.com/x.exe"}]}])
def test_check_ignores(env, data):
    path, _, fake = env
    fake.data = data
    assert u.check("0.1.0", path) is None


def test_network_failure(env, monkeypatch):
    def boom(url):
        raise OSError("down")

    monkeypatch.setattr(u, "_get", boom)
    assert u.check("0.1.0", env[0]) is None


def test_opt_out_env(env, monkeypatch):
    monkeypatch.setenv("SMOOTHSVG_NO_UPDATE", "1")
    assert u.check("0.1.0", env[0]) is None and env[1] == []


def test_opt_out_setting(env):
    path, calls, _ = env
    path.write_text(json.dumps({"check_updates": False}))
    assert u.check("0.1.0", path) is None and calls == []


def _dl(monkeypatch, tmp_path, body, sums_hash):
    name = "smooth-svg-setup-0.2.0.exe"
    monkeypatch.setattr(u._opener, "open", lambda req, timeout=0: io.BytesIO(body))
    monkeypatch.setattr(u, "_get", lambda url: f"{sums_hash}  {name}\n".encode())
    return u.download_and_verify(f"{P}v0.2.0/{name}", f"{P}v0.2.0/SHA256SUMS.txt", tmp_path), tmp_path / name


def test_hash_ok(monkeypatch, tmp_path):
    out, final = _dl(monkeypatch, tmp_path, b"abc", hashlib.sha256(b"abc").hexdigest())
    assert out == final and final.read_bytes() == b"abc" and not list(tmp_path.glob("*.part"))


def test_hash_bad_deletes(monkeypatch, tmp_path):
    out, _ = _dl(monkeypatch, tmp_path, b"abc", "0" * 64)
    assert out is None and list(tmp_path.iterdir()) == []


def test_url_outside_repo_refused(tmp_path):
    assert u.download_and_verify("https://evil.com/a.exe", f"{P}x/SHA256SUMS.txt", tmp_path) is None
    assert not u.url_allowed("http://github.com/PatrikGuerra/smooth-svg/releases/download/x")


def test_launch(monkeypatch, tmp_path):
    seen = []
    monkeypatch.setattr(u.subprocess, "Popen", lambda cmd, **k: seen.append(cmd))
    assert u.launch_installer(tmp_path / "s.exe") and "/VERYSILENT" in seen[0] and "/RESTARTAPPLICATIONS" in seen[0]

    def boom(*a, **k):
        raise OSError

    monkeypatch.setattr(u.subprocess, "Popen", boom)
    assert u.launch_installer(tmp_path / "s.exe") is False


def test_url_allowed_rejects_dotdot():
    assert u.url_allowed(u.ALLOWED_PREFIX + "v1.0.0/x.exe")
    assert not u.url_allowed(u.ALLOWED_PREFIX + "../../other/repo/x.exe")


@pytest.mark.parametrize("new,ok", [("https://objects.githubusercontent.com/x", True), ("https://github.com/x", True),
                                    ("http://objects.githubusercontent.com/x", False), ("https://evil.com/x", False),
                                    ("https://githubusercontent.com.evil.com/x", False)])
def test_redirect_allowlist(new, ok):
    import urllib.error
    import urllib.request
    h, req = u._SafeRedirect(), urllib.request.Request("https://github.com/a")
    if ok:
        assert h.redirect_request(req, None, 302, "Found", {}, new) is not None
    else:
        with pytest.raises(urllib.error.URLError):
            h.redirect_request(req, None, 302, "Found", {}, new)
