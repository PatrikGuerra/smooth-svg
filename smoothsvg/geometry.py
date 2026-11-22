"""Exact rings, partly hidden circles and arc outlines for the stacked tracer.

detect_shapes (drawing.py) only takes whole blobs without holes. This adds three cases, in this
order, for one layer mask:
 1. ring: a blob whose outer outline and every hole fit ellipses -> one evenodd <path> of
    ellipse arcs. One path (not two stacked circles) so the hole keeps showing whatever is
    below it, even transparency.
 2. hidden: the blob is cut by a later layer. An ellipse is fitted (RANSAC) to the edge pixels
    that no later layer touches, then checked against what is known: the visible part must lie
    inside it and it must lie inside visible part + the layers on top.
 3. arcs: the outline splits into straight runs and circle arcs (A commands) within eps.
"""
import cv2
import numpy as np

MAX_SEGMENTS = 24


def _ell_mask(shape, e) -> np.ndarray:
    (cx, cy), (rx, ry), ang = e
    m = np.zeros(shape, np.uint8)
    cv2.ellipse(m, (round(cx * 16), round(cy * 16)), (round(rx * 16), round(ry * 16)), ang,
                0, 360, 1, -1, shift=4)
    return m.astype(bool)


def _iou(a: np.ndarray, b: np.ndarray) -> float:
    union = int((a | b).sum())
    return int((a & b).sum()) / union if union else 0.0


def _fit(c, grow: float | None = None, hole: bool = False):
    """Ellipse (center, radii, angle) of a contour.

    The contour runs through pixel centers, so the fit is a bit off the true edge. With grow
    None the radii are scaled to the pixel area the contour stands for (Pick: pixels = A + B/2 + 1
    for an outline, A - B/2 + 1 for a hole); otherwise grow is added to them.
    """
    (cx, cy), (dw, dh), ang = cv2.fitEllipse(c)
    rx, ry = dw / 2, dh / 2
    if grow is None:
        half = len(c) / 2
        target = cv2.contourArea(c) + (-half if hole else half) + 1
        s = np.sqrt(max(target, 1) / (np.pi * rx * ry))
        return (cx, cy), (rx * s, ry * s), ang
    return (cx, cy), (rx + grow, ry + grow), ang


def _ell_d(e, ox, oy) -> str:
    (cx, cy), (rx, ry), ang = e
    t = np.radians(ang)
    ux, uy = rx * np.cos(t), rx * np.sin(t)
    a, b = (cx + ox - ux, cy + oy - uy), (cx + ox + ux, cy + oy + uy)
    arc = f"A{rx:.1f} {ry:.1f} {ang:.1f} 1 0"
    return f"M{a[0]:.1f} {a[1]:.1f}{arc} {b[0]:.1f} {b[1]:.1f}{arc} {a[0]:.1f} {a[1]:.1f}Z"


def _filled(c, shape) -> np.ndarray:
    m = np.zeros(shape, np.uint8)
    cv2.drawContours(m, [c], -1, 1, -1)
    return m.astype(bool)


def _ring(mask, contours, outer, holes, color, tol, ox, oy):
    """Outer outline plus holes, all ellipses. Returns an SVG element or None."""
    if any(len(contours[i]) < 8 for i in [outer, *holes]) or len(holes) > 4:
        return None
    sh = mask.shape
    out_e = _fit(contours[outer])
    blob = _filled(contours[outer], sh)
    model = _ell_mask(sh, out_e)
    if _iou(blob, model) < 1 - tol:
        return None
    ells = [out_e]
    for h in holes:
        e = _fit(contours[h], hole=True)
        if min(e[1]) < 1 or _iou(_filled(contours[h], sh), _ell_mask(sh, e)) < 1 - tol:
            return None
        blob &= ~_filled(contours[h], sh)
        model &= ~_ell_mask(sh, e)
        ells.append(e)
    if _iou(blob, model) < 1 - tol:
        return None
    d = "".join(_ell_d(e, ox, oy) for e in ells)
    return f'<path fill="{color}" fill-rule="evenodd" d="{d}"/>'


def _ell_dist(e, pts) -> np.ndarray:
    """Approximate distance in px from points to an ellipse."""
    (cx, cy), (rx, ry), ang = e
    t = np.radians(ang)
    dx, dy = pts[:, 0] - cx, pts[:, 1] - cy
    u = dx * np.cos(t) + dy * np.sin(t)
    v = -dx * np.sin(t) + dy * np.cos(t)
    return np.abs(np.hypot(u / rx, v / ry) - 1) * np.sqrt(rx * ry)


def _hidden(shape, own, later, color, tol, ox, oy, rng):
    """Ellipse for a blob that a later layer cuts into. Returns an SVG element or None."""
    cs, _ = cv2.findContours(own.astype(np.uint8), cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_NONE)
    if not cs:
        return None
    c = max(cs, key=cv2.contourArea)
    if cv2.contourArea(c) < 150:
        return None
    pts = c[:, 0, :].astype(float)
    near = cv2.dilate(later.astype(np.uint8), np.ones((5, 5), np.uint8)) > 0
    seen = ~near[c[:, 0, 1], c[:, 0, 0]]
    if seen.all() or seen.sum() < max(12, 0.25 * len(pts)):  # nothing hidden, or too little left
        return None
    vis = pts[seen]
    best, best_n = None, 0
    for _ in range(80):
        s = vis[rng.choice(len(vis), 6, replace=False)]
        try:
            e = cv2.fitEllipse(s.astype(np.float32).reshape(-1, 1, 2))
        except cv2.error:
            continue
        e = (e[0], (e[1][0] / 2, e[1][1] / 2), e[2])
        if min(e[1]) < 3 or max(e[1]) > 3 * min(e[1]) or max(e[1]) > 2 * max(own.shape):
            continue
        n = int((_ell_dist(e, vis) < 1.0).sum())
        if n > best_n:
            best, best_n = e, n
    if best is None or best_n < 0.8 * len(vis):
        return None
    inl = vis[_ell_dist(best, vis) < 1.0]
    e = _fit(inl.astype(np.float32).reshape(-1, 1, 2), 0.25)
    if min(e[1]) < 3 or max(e[1]) > 3 * min(e[1]):
        return None
    m = _ell_mask(own.shape, e)
    if int(m.sum()) == 0 or int((m & later & ~own).sum()) < 0.03 * m.sum():
        return None
    if (own & ~m).sum() > tol * own.sum() or (m & ~(own | later)).sum() > tol * m.sum():
        return None
    (cx, cy), (rx, ry), ang = e
    return (f'<ellipse cx="{cx + ox:.1f}" cy="{cy + oy:.1f}" rx="{rx:.1f}" ry="{ry:.1f}" '
            f'transform="rotate({ang:.1f} {cx + ox:.1f} {cy + oy:.1f})" fill="{color}"/>')


def _circle(pts):
    x, y = pts[:, 0], pts[:, 1]
    a = np.c_[2 * x, 2 * y, np.ones(len(x))]
    sol = np.linalg.lstsq(a, x * x + y * y, rcond=None)[0]
    r2 = sol[2] + sol[0] ** 2 + sol[1] ** 2
    return (sol[0], sol[1], float(np.sqrt(r2))) if r2 > 0 else None


def _line_ok(p, eps):
    d = p[-1] - p[0]
    n = np.hypot(*d)
    if n < 1e-6:
        return False
    return np.abs(d[0] * (p[:, 1] - p[0, 1]) - d[1] * (p[:, 0] - p[0, 0])).max() / n <= eps


def _arc_ok(p, eps, maxr):
    if len(p) < 6:
        return None
    f = _circle(p)
    if f is None or f[2] > maxr:
        return None
    cx, cy, r = f
    if np.abs(np.hypot(p[:, 0] - cx, p[:, 1] - cy) - r).max() > eps:
        return None
    a = np.unwrap(np.arctan2(p[:, 1] - cy, p[:, 0] - cx))
    step = np.diff(a)
    span = a[-1] - a[0]
    # one direction only, under a full turn, and a real bend (sagitta over 2 eps)
    if abs(span) > 1.8 * np.pi or (step * np.sign(span) < -0.05).any():
        return None
    if r * (1 - np.cos(min(abs(span), np.pi) / 2)) < 2 * eps:
        return None
    return f, span


def _longest(p, i, ok):
    """Largest j so that p[i:j+1] passes ok. Assumes longer runs only get worse."""
    n = len(p)
    lo, step = min(i + 2, n - 1), 8
    hi = lo
    while hi < n - 1 and ok(p[i:min(hi + step, n - 1) + 1]):
        hi = min(hi + step, n - 1)
        step *= 2
    top = min(hi + step, n - 1)
    while hi < top:  # binary search in (hi, top]
        mid = (hi + top + 1) // 2
        if ok(p[i:mid + 1]):
            hi = mid
        else:
            top = mid - 1
    return max(hi, lo)


def _arcs(c, mask, color, tol, ox, oy):
    """Outline as lines and arcs, or None. Needs at least one arc."""
    if len(c) < 40:
        return None
    area = cv2.contourArea(c)
    eps = max(0.8, 0.004 * np.sqrt(area))
    poly = cv2.approxPolyDP(c, 2 * eps, True)
    start = int(np.flatnonzero((c[:, 0, :] == poly[0, 0]).all(axis=1))[0])
    p = np.roll(c[:, 0, :].astype(float), -start, axis=0)
    p = np.vstack([p, p[:1]])
    maxr = 4 * max(mask.shape)
    segs, i = [], 0
    while i < len(p) - 1:
        jl = _longest(p, i, lambda q: _line_ok(q, eps))
        ja = _longest(p, i, lambda q: _arc_ok(q, eps, maxr) is not None)
        arc = _arc_ok(p[i:ja + 1], eps, maxr) if ja > jl + 2 else None
        if arc:
            segs.append((i, ja, arc))
            i = ja
        else:
            segs.append((i, jl, None))
            i = jl
        if len(segs) > MAX_SEGMENTS:
            return None
    if not any(s[2] for s in segs):
        return None
    d, ring = f"M{p[0, 0] + ox:.1f} {p[0, 1] + oy:.1f}", [p[0]]
    for a, b, arc in segs:
        x, y = p[b]
        if arc:
            (cx, cy, r), span = arc
            d += f"A{r:.1f} {r:.1f} 0 {int(abs(span) > np.pi)} {int(span > 0)} {x + ox:.1f} {y + oy:.1f}"
            a0 = np.arctan2(p[a, 1] - cy, p[a, 0] - cx)
            t = a0 + span * np.linspace(0, 1, 16)[1:]
            ring += list(np.c_[cx + r * np.cos(t), cy + r * np.sin(t)])
        else:
            d += f"L{x + ox:.1f} {y + oy:.1f}"
        ring.append(p[b])
    model = np.zeros(mask.shape, np.uint8)
    cv2.fillPoly(model, [np.round(np.array(ring)).astype(np.int32)], 1)
    if _iou(_filled(c, mask.shape), model.astype(bool)) < 1 - tol / 2:
        return None
    return f'<path fill="{color}" d="{d}Z"/>'


def detect_geometry(shape, own, later, color, tol, ox=0, oy=0, min_area=60):
    """Rings, hidden circles and arc outlines in one layer.

    shape: the mask about to be traced; own, later: this piece alone and the pieces on top of it
    (same crop). Returns (shape without the found blobs, list of SVG elements).
    """
    contours, hier = cv2.findContours(shape.astype(np.uint8), cv2.RETR_CCOMP, cv2.CHAIN_APPROX_NONE)
    if hier is None:
        return shape, []
    rest, found = shape.copy(), []
    tops = [i for i in range(len(contours)) if hier[0][i][3] == -1]
    if len(tops) == 1 and hier[0][tops[0]][2] == -1 and later.any():
        el = _hidden(shape, own, later, color, tol, ox, oy, np.random.default_rng(0))
        if el:
            return np.zeros_like(shape), [el]
    for i in tops:
        c = contours[i]
        if cv2.contourArea(c) < min_area:
            continue
        holes, k = [], hier[0][i][2]
        while k != -1:
            holes.append(k)
            k = hier[0][k][0]
        el = (_ring(shape, contours, i, holes, color, tol, ox, oy) if holes
              else _arcs(c, shape, color, tol, ox, oy))
        if el:
            found.append(el)
            rest &= ~(_filled(c, shape.shape))
    return rest, found
