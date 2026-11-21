"""Auto update (PLANO-APP-WINDOWS.md, secao 7). Stdlib only; never raises to the caller."""

from __future__ import annotations

import contextlib
import hashlib
import json
import logging
import os
import re
import subprocess
import tempfile
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

log = logging.getLogger("smoothsvg.updater")

REPO = "PatrikGuerra/smooth-svg"
API_URL = f"https://api.github.com/repos/{REPO}/releases/latest"
ALLOWED_PREFIX = f"https://github.com/{REPO}/releases/download/"
CACHE_SECONDS = 24 * 3600
TIMEOUT = 5
_TAG_RE = re.compile(r"^v\d+\.\d+\.\d+$")
INSTALLER_FLAGS = ["/VERYSILENT", "/SUPPRESSMSGBOXES", "/NORESTART", "/CLOSEAPPLICATIONS", "/RESTARTAPPLICATIONS"]


def settings_path() -> Path:
    base = os.environ.get("APPDATA") or str(Path.home())
    return Path(base) / "smooth-svg" / "settings.json"


def _load(path: Path) -> dict:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except Exception:  # noqa: BLE001 - fail safe
        return {}


def _save(path: Path, data: dict) -> None:
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(data), encoding="utf-8")
    except Exception as e:  # noqa: BLE001 - fail safe
        log.warning("settings not saved: %s", e)


def parse_version(v: str) -> tuple[int, int, int] | None:
    """'v1.2.3' or '1.2.3' -> (1, 2, 3); anything else (rc, 2 parts) -> None.

    shortcut: semver only with 3 numbers, no pre-release; use packaging.version if rc ever ships.
    """
    if not isinstance(v, str):
        return None
    v = v if v.startswith("v") else "v" + v
    if not _TAG_RE.match(v):
        return None
    a, b, c = (int(x) for x in v[1:].split("."))
    return a, b, c


def is_newer(candidate: str, current: str) -> bool:
    c, k = parse_version(candidate), parse_version(current)
    return c is not None and k is not None and c > k


def url_allowed(url: str) -> bool:
    return isinstance(url, str) and url.startswith(ALLOWED_PREFIX) and ".." not in url


class _SafeRedirect(urllib.request.HTTPRedirectHandler):
    """GitHub redirects downloads to *.githubusercontent.com; accept only that over https."""

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        host = urllib.parse.urlparse(newurl)
        h = host.hostname or ""
        if host.scheme != "https" or not (h == "github.com" or h.endswith(".githubusercontent.com")):
            raise urllib.error.URLError(f"redirect refused: {newurl}")
        return super().redirect_request(req, fp, code, msg, headers, newurl)


_opener = urllib.request.build_opener(_SafeRedirect)


def _get(url: str) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": "smooth-svg-updater", "Accept": "application/vnd.github+json"})
    with _opener.open(req, timeout=TIMEOUT) as r:
        return r.read()


def _parse_release(data: dict, current: str) -> dict | None:
    if data.get("draft") or data.get("prerelease"):
        return None
    tag = data.get("tag_name")
    if not isinstance(tag, str) or not _TAG_RE.match(tag) or not is_newer(tag, current):
        return None
    urls = {a.get("name"): a.get("browser_download_url") for a in data.get("assets", []) if isinstance(a, dict)}
    version = tag[1:]
    exe, sums = urls.get(f"smooth-svg-setup-{version}.exe"), urls.get("SHA256SUMS.txt")
    if not (url_allowed(exe) and url_allowed(sums)):
        return None
    return {"version": version, "url": exe, "sums_url": sums}


def check(current: str, path: Path | None = None) -> dict | None:
    """Return {'version','url','sums_url'} when a newer release exists, else None. Never raises."""
    try:
        if os.environ.get("SMOOTHSVG_NO_UPDATE"):
            return None
        path = path or settings_path()
        s = _load(path)
        if s.get("check_updates") is False:
            return None
        last = s.get("last_check")
        if isinstance(last, (int, float)) and time.time() - last < CACHE_SECONDS:
            cached = s.get("last_result")
            if isinstance(cached, dict) and is_newer(cached.get("version", ""), current) and url_allowed(cached.get("url")) and url_allowed(cached.get("sums_url")):
                return cached
            return None
        result = _parse_release(json.loads(_get(API_URL)), current)
        s["last_check"], s["last_result"] = time.time(), result
        _save(path, s)
        return result
    except Exception as e:  # noqa: BLE001 - fail safe
        log.warning("update check failed: %s", e)
        return None


def _sha256(p: Path) -> str:
    h = hashlib.sha256()
    with p.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _expected_hash(sums: str, name: str) -> str | None:
    for line in sums.splitlines():
        parts = line.split()
        if len(parts) == 2 and parts[1].lstrip("*") == name:
            return parts[0].lower()
    return None


def download_and_verify(url: str, sums_url: str, dest_dir: Path | None = None) -> Path | None:
    """Download installer to .part, verify against SHA256SUMS.txt, rename to .exe. None on any failure."""
    part = None
    try:
        if not (url_allowed(url) and url_allowed(sums_url)):
            return None
        dest_dir = dest_dir or Path(tempfile.gettempdir()) / "smooth-svg-update"
        dest_dir.mkdir(parents=True, exist_ok=True)
        name = url.rsplit("/", 1)[-1]
        part, final = dest_dir / (name + ".part"), dest_dir / name
        with _opener.open(urllib.request.Request(url, headers={"User-Agent": "smooth-svg-updater"}), timeout=TIMEOUT) as r, part.open("wb") as f:
            while chunk := r.read(1 << 20):
                f.write(chunk)
        expected = _expected_hash(_get(sums_url).decode("utf-8", "replace"), name)
        if expected is None or _sha256(part) != expected:
            log.warning("hash mismatch for %s", name)
            part.unlink(missing_ok=True)
            return None
        os.replace(part, final)
        return final
    except Exception as e:  # noqa: BLE001 - fail safe
        log.warning("download failed: %s", e)
        if part:
            with contextlib.suppress(OSError):
                part.unlink(missing_ok=True)
        return None


def launch_installer(path: Path) -> bool:
    """Start the installer; True only if Popen returned (caller exits the app after that)."""
    try:
        subprocess.Popen([str(path), *INSTALLER_FLAGS], close_fds=True)
        return True
    except Exception as e:  # noqa: BLE001 - fail safe
        log.warning("installer not started: %s", e)
        return False
