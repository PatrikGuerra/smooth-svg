"""Last pass on a finished SVG: find outline stretches that are really circles or ellipses.

Reads the points of every <path> (M L H V C S Q T A Z, absolute or relative, similarity
transforms), sweeps each subpath for runs of curve segments that one circle or ellipse arc
reproduces within a tolerance, and swaps them for an exact A command (or a <circle>/<ellipse>
when the whole path is one). Every swap is then checked by rendering: a swap that makes the
picture closer to the source image worse is undone. Own parser, no new dependency (svgpathtools
is MIT and fine for licensing, but needs scipy-free numpy plus its own object model for ~150
lines we would still have to write around it).

shortcut: no RANSAC; a window grows segment by segment and the max deviation of the real
endpoint-pinned arc is the test, so outliers just end the window. Upgrade if noisy JPG
outlines need arcs through bumps.
"""
import math
import re

import cv2
import numpy as np

from .score import render

_CMD = "MmLlHhVvCcSsQqTtAaZz"
_NUM = re.compile(r"[-+]?(?:\d+\.?\d*|\.\d+)(?:[eE][-+]?\d+)?")
_ARITY = {"M": 2, "L": 2, "H": 1, "V": 1, "C": 6, "S": 4, "Q": 4, "T": 2, "A": 7, "Z": 0}
_PATH = re.compile(r"<path\b[^>]*?/>")
_ATTR = re.compile(r'([\w:-]+)="([^"]*)"')
MAX_RENDER_PX = 4_000_000


def _tokens(d: str):
    """Yield (command, [numbers]) groups. Arc flags may be glued to the next number."""
    i, n, cmd, args = 0, len(d), None, []
    while i < n:
        ch = d[i]
        if ch in " ,\t\r\n":
            i += 1
        elif ch in _CMD:
            cmd, args = ch, []
            i += 1
            if ch in "Zz":
                yield ch, []
                cmd = None
        elif cmd is None:
            raise ValueError("number before a command")
        else:
            flag = cmd in "Aa" and len(args) % 7 in (3, 4)
            if flag:
                if ch not in "01":
                    raise ValueError("bad arc flag")
                args.append(float(ch))
                i += 1
            else:
                m = _NUM.match(d, i)
                if not m:
                    raise ValueError(f"bad path data at {i}")
                args.append(float(m.group()))
                i = m.end()
            if len(args) == _ARITY[cmd.upper()]:
                yield cmd, args
                args = []
                if cmd in "Mm":
                    cmd = "l" if cmd == "m" else "L"
    if args:
        raise ValueError("incomplete command")


def parse_path(d: str):
    """Path data to subpaths: {segs, closed}. A seg is ('L'|'C'|'A', ...) with absolute points."""
    subs, cur, start, last_c = [], None, None, None
    pt = np.zeros(2)
    prev = ""

    def begin(p):
        nonlocal cur, start
        cur = {"segs": [], "closed": False}
        subs.append(cur)
        start = p.copy()

    for cmd, a in _tokens(d):
        rel, up = cmd.islower(), cmd.upper()
        if up == "Z":
            if cur is not None:
                if np.hypot(*(pt - start)) > 1e-9:
                    cur["segs"].append(("L", pt.copy(), start.copy()))
                cur["closed"] = True
                pt = start.copy()
                cur = None
            prev = "Z"
            continue
        if up != "M" and cur is None:
            begin(pt)  # drawing after Z starts a new subpath at the old start
        o = pt if rel else np.zeros(2)
        if up == "M":
            pt = o + np.array(a[:2])
            begin(pt)
        elif up in "LHV":
            q = pt.copy()
            if up == "L":
                q = o + np.array(a)
            elif up == "H":
                q[0] = a[0] + (pt[0] if rel else 0)
            else:
                q[1] = a[0] + (pt[1] if rel else 0)
            cur["segs"].append(("L", pt.copy(), q))
            pt = q
        elif up in "CS":
            if up == "C":
                c1, c2, q = (o + np.array(a[i:i + 2]) for i in (0, 2, 4))
            else:
                c1 = 2 * pt - last_c if prev in "CS" else pt.copy()
                c2, q = (o + np.array(a[i:i + 2]) for i in (0, 2))
            cur["segs"].append(("C", pt.copy(), c1, c2, q))
            last_c, pt = c2, q
        elif up in "QT":
            if up == "Q":
                c, q = (o + np.array(a[i:i + 2]) for i in (0, 2))
            else:
                c = 2 * pt - last_c if prev in "QT" else pt.copy()
                q = o + np.array(a)
            cur["segs"].append(
                ("C", pt.copy(), pt + 2 / 3 * (c - pt), q + 2 / 3 * (c - q), q))
            last_c, pt = c, q
        else:  # A
            q = o + np.array(a[5:7])
            cur["segs"].append(("A", pt.copy(), q, a[0], a[1], a[2], int(a[3]), int(a[4])))
            pt = q
        prev = up
    return subs


def _transform(s: str | None):
    """transform attribute to a 2x3 matrix, or None when it is not a similarity (or unknown)."""
    m = np.eye(3)
    for name, body in re.findall(r"(\w+)\s*\(([^)]*)\)", s or ""):
        v = [float(x) for x in _NUM.findall(body)]
        t = np.eye(3)
        if name == "translate" and len(v) in (1, 2):
            t[:2, 2] = (v[0], v[1] if len(v) == 2 else 0)
        elif name == "scale" and len(v) in (1, 2):
            t[0, 0], t[1, 1] = v[0], v[-1]
        elif name == "rotate" and len(v) in (1, 3):
            c, sn = math.cos(math.radians(v[0])), math.sin(math.radians(v[0]))
            t[:2, :2] = [[c, -sn], [sn, c]]
            if len(v) == 3:
                t[:2, 2] = np.array(v[1:]) - t[:2, :2] @ v[1:]
        elif name == "matrix" and len(v) == 6:
            t[:2] = np.array(v).reshape(3, 2).T
        else:
            return None
        m = m @ t
    a, b, c, d = m[0, 0], m[1, 0], m[0, 1], m[1, 1]
    if abs(a - d) > 1e-6 * max(1, abs(a)) or abs(b + c) > 1e-6 * max(1, abs(b)) or a * d - b * c <= 0:
        return None
    return m


# ---------------------------------------------------------------- geometry

def _circle(P: np.ndarray, refine: bool = True):
    """Least squares circle (Kasa start, then Gauss-Newton on the true distance). (c, r) or None."""
    m = P.mean(axis=0)
    Q = P - m
    if len(Q) < 3 or np.ptp(Q, axis=0).max() < 1e-9:
        return None
    A = np.c_[2 * Q, np.ones(len(Q))]
    try:
        sol = np.linalg.lstsq(A, (Q ** 2).sum(axis=1), rcond=None)[0]
    except np.linalg.LinAlgError:
        return None
    c = sol[:2]
    r2 = sol[2] + c @ c
    if not np.isfinite(r2) or r2 <= 0:
        return None
    r = math.sqrt(r2)
    for _ in range(6 if refine else 0):
        v = Q - c
        dist = np.hypot(v[:, 0], v[:, 1])
        if dist.min() < 1e-12:
            break
        J = np.c_[-v / dist[:, None], -np.ones(len(Q))]
        step = np.linalg.lstsq(J, dist - r, rcond=None)[0]
        c, r = c - step[:2], r - step[2]
    return c + m, abs(r)


def _arc(p0, p1, rx, ry, phi, fa, fs):
    """SVG endpoint arc to (center, theta1, dtheta, rx, ry), spec F.6.5-F.6.6. None if degenerate."""
    if rx <= 0 or ry <= 0 or np.hypot(*(p1 - p0)) < 1e-12:
        return None
    c, s = math.cos(math.radians(phi)), math.sin(math.radians(phi))
    dx, dy = (p0 - p1) / 2
    x1, y1 = c * dx + s * dy, -s * dx + c * dy
    lam = x1 * x1 / (rx * rx) + y1 * y1 / (ry * ry)
    if lam > 1:
        rx, ry = rx * math.sqrt(lam), ry * math.sqrt(lam)
    num = rx * rx * ry * ry - rx * rx * y1 * y1 - ry * ry * x1 * x1
    den = rx * rx * y1 * y1 + ry * ry * x1 * x1
    k = (1 if fa != fs else -1) * math.sqrt(max(0.0, num / den)) if den else 0.0
    cxp, cyp = k * rx * y1 / ry, -k * ry * x1 / rx
    ctr = np.array([c * cxp - s * cyp, s * cxp + c * cyp]) + (p0 + p1) / 2
    t1 = math.atan2((y1 - cyp) / ry, (x1 - cxp) / rx)
    t2 = math.atan2((-y1 - cyp) / ry, (-x1 - cxp) / rx)
    dt = t2 - t1
    if fs and dt < 0:
        dt += 2 * math.pi
    elif not fs and dt > 0:
        dt -= 2 * math.pi
    return ctr, t1, dt, rx, ry


def _arc_pts(ctr, t1, dt, rx, ry, phi, step=0.5):
    n = int(np.clip(abs(dt) * max(rx, ry) / step, 16, 4000))
    t = t1 + dt * np.linspace(0, 1, n)
    c, s = math.cos(math.radians(phi)), math.sin(math.radians(phi))
    x, y = rx * np.cos(t), ry * np.sin(t)
    return np.c_[c * x - s * y, s * x + c * y] + ctr


def _dist(P: np.ndarray, L: np.ndarray) -> np.ndarray:
    """Distance from each point of P to the polyline L."""
    a, b = L[:-1][None], L[1:][None]
    ab = b - a
    ap = P[:, None] - a
    t = np.clip((ap * ab).sum(-1) / np.maximum((ab * ab).sum(-1), 1e-18), 0, 1)
    d = ap - t[..., None] * ab
    return np.sqrt((d * d).sum(-1)).min(axis=1)


def _within(dev, rms, tol):
    """tol is the RMS limit (x0.8); the worst point may stray up to 1.75 tol (outlines are not exact)."""
    return dev <= 1.75 * tol and rms <= 0.8 * tol


def _radial(P, ctr, rx, ry, phi):
    """Rough max distance of P from the ellipse, from the normalized radius."""
    c, s = math.cos(math.radians(phi)), math.sin(math.radians(phi))
    v = (P - ctr) @ np.array([[c, s], [-s, c]]).T
    return float(np.abs(np.hypot(v[:, 0] / rx, v[:, 1] / ry) - 1).max() * min(rx, ry))


def _flags(P, ctr, rx, ry, phi):
    """Direction and size of the sweep that walks P around the ellipse: (fa, fs)."""
    c, s = math.cos(math.radians(phi)), math.sin(math.radians(phi))
    v = (P - ctr) @ np.array([[c, s], [-s, c]]).T  # into the ellipse frame
    th = np.unwrap(np.arctan2(v[:, 1] / ry, v[:, 0] / rx))
    tot = th[-1] - th[0]
    return int(abs(tot) > math.pi), int(tot > 0), abs(tot)


def _try(P, p0, p1, ctr, rx, ry, phi, tol, min_sweep, rmax, ppu):
    """Pin an arc of this ellipse to p0, p1; the result if it stays within tol of P, else None."""
    fa, fs, tot = _flags(P, ctr, rx, ry, phi)
    if tot > math.radians(280):
        return None
    cand = _arc(p0, p1, rx, ry, phi, fa, fs)
    if cand is None:
        return None
    ctr2, t1, dt, rx2, ry2 = cand
    if abs(dt) < math.radians(min_sweep) or abs(dt) * min(rx2, ry2) * ppu < 4:
        return None
    if rx2 == ry2:  # circle: radial distance is the exact distance, no polyline needed
        d1 = np.abs(np.hypot(*(P - ctr2).T) - rx2)
        dev = d1.max()
    else:
        if _radial(P, ctr2, rx2, ry2, phi) > 2.2 * tol:  # cheap reject before the polyline test
            return None
        A = _arc_pts(ctr2, t1, dt, rx2, ry2, phi)
        d1 = _dist(P, A)
        dev = max(d1.max(), _dist(A[::4], P).max())
    rms = float(np.sqrt((d1 ** 2).mean()))
    if not _within(dev, rms, tol):
        return None
    return {"rx": rx2, "ry": ry2, "phi": phi, "fa": fa, "fs": fs, "dev": dev,
            "rms": rms, "sweep": abs(dt), "ctr": ctr2}


def fit_window(P, tol, min_sweep, rmax, ppu):
    """Best circle (else ellipse) arc through the ends of the points P, or None."""
    p0, p1 = P[0], P[-1]
    best = None
    cr = _circle(P, refine=False)
    if cr is not None and np.abs(np.hypot(*(P - cr[0]).T) - cr[1]).max() > 3 * tol:
        cr = None  # not even roughly round: skip the exact fit
    elif cr is not None:
        cr = _circle(P)
    if cr is not None and cr[1] <= rmax:
        (c, r) = cr
        cands = [r]
        a, b, m = p0, p1, P[len(P) // 2]
        cross = (b[0] - a[0]) * (m[1] - a[1]) - (b[1] - a[1]) * (m[0] - a[0])
        if abs(cross) > 1e-9:
            r3 = np.hypot(*(a - b)) * np.hypot(*(a - m)) * np.hypot(*(b - m)) / (2 * abs(cross))
            if r3 <= rmax:
                cands.append(r3)
        for rr in cands:
            o = _try(P, p0, p1, c, rr, rr, 0.0, tol, min_sweep, rmax, ppu)
            if o and (best is None or o["dev"] < best["dev"]):
                best = o
        if best:
            best["kind"] = "circle"
            return best
    if len(P) >= 12:
        try:
            (cx, cy), (w, h), ang = cv2.fitEllipse(P.astype(np.float32).reshape(-1, 1, 2))
        except cv2.error:
            return None
        rx, ry = w / 2, h / 2
        if min(rx, ry) * ppu >= 2 and max(rx, ry) <= rmax and max(rx, ry) / min(rx, ry) <= 4:
            o = _try(P, p0, p1, np.array([cx, cy]), rx, ry, ang, tol, max(min_sweep, 45), rmax, ppu)
            if o:
                o["kind"] = "ellipse"
                return o
    return None


def fit_closed(P, tol, rmax, ppu):
    """Whole closed outline as one circle or ellipse: dict(ctr, rx, ry, phi) or None."""
    cr = _circle(P)
    if cr is not None and cr[1] <= rmax and cr[1] * ppu >= 2:
        c, r = cr
        d = np.abs(np.hypot(*(P - c).T) - r)
        if _within(d.max(), float(np.sqrt((d ** 2).mean())), tol):
            return {"ctr": c, "rx": r, "ry": r, "phi": 0.0}
    if len(P) < 12:
        return None
    try:
        (cx, cy), (w, h), ang = cv2.fitEllipse(P.astype(np.float32).reshape(-1, 1, 2))
    except cv2.error:
        return None
    rx, ry = w / 2, h / 2
    if min(rx, ry) * ppu < 2 or max(rx, ry) > rmax or max(rx, ry) / min(rx, ry) > 4:
        return None
    ctr = np.array([cx, cy])
    if _radial(P, ctr, rx, ry, ang) > 2.2 * tol:
        return None
    E = _arc_pts(ctr, 0, 2 * math.pi, rx, ry, ang)
    d = _dist(P, E)
    if not _within(max(d.max(), _dist(E[::4], P).max()), float(np.sqrt((d ** 2).mean())), tol):
        return None
    return {"ctr": ctr, "rx": rx, "ry": ry, "phi": ang}


# ---------------------------------------------------------------- sampling and search

def _sample(seg, ppu):
    if seg[0] == "L":
        return np.array([seg[1], seg[2]])
    if seg[0] == "A":
        cand = _arc(seg[1], seg[2], seg[3], seg[4], seg[5], seg[6], seg[7])
        if cand is None:
            return np.array([seg[1], seg[2]])
        ctr, t1, dt, rx, ry = cand
        return _arc_pts(ctr, t1, dt, rx, ry, seg[5])
    _, p0, c1, c2, p1 = seg
    n = int(np.clip(math.ceil((np.hypot(*(c1 - p0)) + np.hypot(*(c2 - c1)) + np.hypot(*(p1 - c2)))
                              * ppu), 8, 80))
    t = np.linspace(0, 1, n)[:, None]
    return (1 - t) ** 3 * p0 + 3 * (1 - t) ** 2 * t * c1 + 3 * (1 - t) * t ** 2 * c2 + t ** 3 * p1


def _dirs(seg):
    """Unit tangent at the start and end of a segment (None when it has no length)."""
    pts = ([seg[1], seg[2]] if seg[0] in "LA" else [seg[1], seg[2], seg[3], seg[4]])
    def unit(a, b):
        v = b - a
        n = np.hypot(*v)
        return v / n if n > 1e-9 else None
    ins = next((u for u in (unit(pts[i], pts[i + 1]) for i in range(len(pts) - 1)) if u is not None), None)
    outs = next((u for u in (unit(pts[i - 1], pts[i]) for i in range(len(pts) - 1, 0, -1))
                 if u is not None), None)
    return ins, outs


def _corners(segs, closed):
    """corner[k] is True when a sharp turn sits between segment k and k+1 (cyclic if closed)."""
    n = len(segs)
    ds = [_dirs(s) for s in segs]
    out = []
    for k in range(n):
        if k == n - 1 and not closed:
            out.append(True)
            continue
        a, b = ds[k][1], ds[(k + 1) % n][0]
        out.append(a is None or b is None or float(a @ b) < math.cos(math.radians(35)))
    return out


def _search(segs, closed, tol, min_sweep, rmax, ppu):
    """Greedy left-to-right windows: [(i, j, fit)] meaning segments i..j-1 become one arc."""
    n = len(segs)
    samples = [_sample(s, ppu) for s in segs]
    corner = _corners(segs, closed)
    ok = [s[0] == "C" for s in segs]
    wins, i = [], 0
    while i < n:
        if not ok[i]:
            i += 1
            continue
        best, j, miss = None, i, 0
        while j < n and ok[j]:
            j += 1
            P = np.vstack([samples[i]] + [s[1:] for s in samples[i + 1:j]])
            f = fit_window(P, tol, min_sweep, rmax, ppu)
            if f:
                best, miss = (j, f), 0
            else:
                miss += 1
                if miss > 1 and best:
                    break
                if miss > 3:
                    break
            if corner[j - 1]:
                break
        if best:
            wins.append((i, best[0], best[1]))
            i = best[0]
        else:
            i += 1
    return wins, samples


# ---------------------------------------------------------------- output

def _f(v: float) -> str:
    s = f"{v:.3f}".rstrip("0").rstrip(".")
    return "0" if s in ("-0", "") else s


def _pt(p) -> str:
    return f"{_f(p[0])} {_f(p[1])}"


def _emit_seg(seg) -> str:
    if seg[0] == "L":
        return f"L{_pt(seg[2])}"
    if seg[0] == "C":
        return f"C{_pt(seg[2])} {_pt(seg[3])} {_pt(seg[4])}"
    return f"A{_f(seg[3])} {_f(seg[4])} {_f(seg[5])} {seg[6]} {seg[7]} {_pt(seg[2])}"


def _arc_cmd(f, p1) -> str:
    return f"A{_f(f['rx'])} {_f(f['ry'])} {_f(f['phi'])} {f['fa']} {f['fs']} {_pt(p1)}"


def _sub_text(sub, units):
    """Path data for one subpath; units = [(i, j, fit)] sorted, or 'whole' fit dict."""
    segs = sub["segs"]
    if isinstance(units, dict):  # whole outline
        w = units
        c, s = math.cos(math.radians(w["phi"])), math.sin(math.radians(w["phi"]))
        v = (segs[0][1] - w["ctr"]) @ np.array([[c, s], [-s, c]]).T
        th = math.atan2(v[1] / w["ry"], v[0] / w["rx"])
        ends = [w["ctr"] + np.array([[c, -s], [s, c]]) @ (np.array([w["rx"] * math.cos(t),
                                                                     w["ry"] * math.sin(t)]))
                for t in (th, th + math.pi)]
        P = np.vstack([_sample(g, 1) for g in segs])
        fs = _flags(P, w["ctr"], w["rx"], w["ry"], w["phi"])[1]
        arc = {"rx": w["rx"], "ry": w["ry"], "phi": w["phi"], "fa": 0, "fs": fs}
        return f"M{_pt(ends[0])}{_arc_cmd(arc, ends[1])}{_arc_cmd(arc, ends[0])}Z"
    out, k, u = [f"M{_pt(segs[0][1])}"], 0, list(units)
    while k < len(segs):
        if u and u[0][0] == k:
            _, j, f = u.pop(0)
            out.append(_arc_cmd(f, segs[j - 1][-1] if segs[j - 1][0] != "A" else segs[j - 1][2]))
            k = j
        else:
            out.append(_emit_seg(segs[k]))
            k += 1
    return "".join(out) + ("Z" if sub["closed"] else "")


def _rotate(sub):
    """Start a closed outline right after a sharp corner, so no arc has to wrap around the start."""
    segs = sub["segs"]
    if not sub["closed"] or len(segs) < 2:
        return
    c = _corners(segs, True)
    if True in c:
        k = c.index(True) + 1
        sub["segs"] = segs[k:] + segs[:k]


# ---------------------------------------------------------------- driver

def _parse_svg(svg: str):
    head = re.search(r"<svg\b[^>]*>", svg)
    if not head:
        raise ValueError("no <svg>")
    attrs = dict(_ATTR.findall(head.group()))
    w = float(_NUM.match(attrs["width"]).group())
    vb = [float(x) for x in _NUM.findall(attrs.get("viewBox", ""))] or [0, 0, w, 0]
    h = float(_NUM.match(attrs["height"]).group())
    if len(vb) != 4 or vb[2] <= 0 or w <= 0 or h <= 0:
        raise ValueError("bad size")
    return w, h, vb


def fit(svg: str, ref: np.ndarray | None = None, tol: float = 0.35, min_sweep: float = 25.0):
    """Swap circular/elliptical stretches of the paths in svg for exact arcs.

    tol is in pixels of the source image (width attribute); ref, the source as RGB uint8 (white
    behind transparency), turns on the render check. Returns (svg, stats). Anything it cannot
    read is left as it was; bad input gives the input back.
    """
    stats = {"arcs": 0, "circles": 0, "ellipses": 0, "tried": 0, "undone": 0}
    try:
        w, h, vb = _parse_svg(svg)
    except (ValueError, KeyError, AttributeError):
        return svg, stats
    k = vb[2] / w  # viewBox units per source pixel
    items, units = [], []  # items: (match span, attrs, subs, matrix, ppu)
    for m in _PATH.finditer(svg):
        at = dict(_ATTR.findall(m.group()))
        mat = _transform(at.get("transform"))
        if "d" not in at or mat is None:
            continue
        try:
            subs = parse_path(at["d"])
        except (ValueError, IndexError):
            continue
        ppu = math.hypot(mat[0, 0], mat[1, 0]) / k  # source px per local unit
        tol_l, rmax = tol / ppu, 4 * max(vb[2], vb[3]) / math.hypot(mat[0, 0], mat[1, 0])
        item = {"span": m.span(), "at": at, "subs": subs, "mat": mat, "ppu": ppu, "found": {}}
        for si, sub in enumerate(subs):
            if len(sub["segs"]) < 2 or any(s[0] == "A" for s in sub["segs"]):
                continue
            _rotate(sub)
            segs = sub["segs"]
            if sub["closed"] and all(s[0] == "C" for s in segs):
                P = np.vstack([_sample(s, ppu) for s in segs])
                whole = fit_closed(P, tol_l, rmax, ppu)
                if whole:
                    item["found"][si] = [("whole", whole, P)]
                    continue
            wins, samples = _search(segs, sub["closed"], tol_l, min_sweep, rmax, ppu)
            if wins:
                item["found"][si] = [("win", (i, j, f), np.vstack(samples[i:j])) for i, j, f in wins]
        if item["found"]:
            items.append(item)
    if not items:
        return svg, stats
    for ii, it in enumerate(items):
        for si, lst in it["found"].items():
            for ui, (kind, data, P) in enumerate(lst):
                q = (P @ it["mat"][:2, :2].T + it["mat"][:2, 2]) / k  # source pixels
                units.append({"key": (ii, si, ui), "box": (*q.min(axis=0) - 2, *q.max(axis=0) + 2)})
    stats["tried"] = len(units)
    on = {u["key"] for u in units}

    def build(on):
        out, last = [], 0
        for ii, it in enumerate(items):
            mine = {si: [(ui, u) for ui, u in enumerate(lst) if (ii, si, ui) in on]
                    for si, lst in it["found"].items()}
            if not any(mine.values()):
                continue
            ds, elem = [], None
            for si, sub in enumerate(it["subs"]):
                use = mine.get(si)
                if not use:
                    ds.append(_sub_text(sub, []))
                elif use[0][1][0] == "whole":
                    w_ = use[0][1][1]
                    if len(it["subs"]) == 1:
                        elem = w_
                    ds.append(_sub_text(sub, w_))
                else:
                    ds.append(_sub_text(sub, [u[1][1] for u in use]))
            a, b = it["span"]
            out.append(svg[last:a])
            at = {x: v for x, v in it["at"].items() if x != "d"}
            if elem:
                out.append(_shape(elem, at))
            else:
                at["d"] = "".join(ds)
                out.append("<path " + " ".join(f'{x}="{v}"' for x, v in at.items()) + "/>")
            last = b
        out.append(svg[last:])
        return "".join(out)

    if ref is not None and ref.size:
        on = _validate(svg, build, on, units, ref, w, h)
    stats["undone"] = len(units) - len(on)
    if not on:
        return svg, stats
    res = build(on)
    for ii, si, ui in on:
        kind, data, _ = items[ii]["found"][si][ui]
        if kind == "win":
            stats["arcs"] += 1
        elif len(items[ii]["subs"]) == 1:
            stats["circles" if abs(data["rx"] - data["ry"]) < 1e-3 * data["rx"] else "ellipses"] += 1
        else:
            stats["arcs"] += 2
    return res, stats


def _shape(w, at):
    """<circle> or <ellipse> for a whole-path fit; a tilt goes into the transform."""
    cx, cy = _f(w["ctr"][0]), _f(w["ctr"][1])
    tr = at.get("transform", "")
    rest = " ".join(f'{x}="{v}"' for x, v in at.items() if x != "transform")
    if abs(w["rx"] - w["ry"]) < 1e-3 * w["rx"]:
        tag = f'<circle cx="{cx}" cy="{cy}" r="{_f((w["rx"] + w["ry"]) / 2)}"'
    else:
        tag = f'<ellipse cx="{cx}" cy="{cy}" rx="{_f(w["rx"])}" ry="{_f(w["ry"])}"'
        if abs(w["phi"] % 180) > 1e-3:
            tr = f"{tr} rotate({_f(w['phi'])} {cx} {cy})".strip()
    return f"{tag} {rest}" + (f' transform="{tr}"' if tr else "") + "/>"


def _validate(svg, build, on, units, ref, w, h):
    """Keep only the swaps that do not make the render farther from the source image."""
    H, W = ref.shape[:2]
    f = min(1.0, (MAX_RENDER_PX / (H * W)) ** 0.5)
    rw, rh = max(1, round(W * f)), max(1, round(H * f))
    r = ref if f == 1 else cv2.resize(ref, (rw, rh), interpolation=cv2.INTER_AREA)
    r = r.astype(np.int16)

    def err(s):
        return np.abs(render(s, rw, rh).astype(np.int16) - r).sum(axis=2).astype(np.int64)

    old = err(svg)
    box = {u["key"]: u["box"] for u in units}
    sx, sy = rw / w, rh / h
    for _ in range(6):
        new = err(build(on))
        bad = set()
        for key in on:
            x0, y0, x1, y1 = box[key]
            xs = slice(max(0, int(x0 * sx)), min(rw, math.ceil(x1 * sx) + 1))
            ys = slice(max(0, int(y0 * sy)), min(rh, math.ceil(y1 * sy) + 1))
            slack = 5 * (x1 - x0 + y1 - y0) * min(sx, sy)  # under 1% of an edge pixel: render noise
            if new[ys, xs].sum() > old[ys, xs].sum() + slack:
                bad.add(key)
        if not bad:
            break
        on = on - bad
        if not on:
            break
    return on
