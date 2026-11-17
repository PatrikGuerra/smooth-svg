import cv2
import numpy as np

SAMPLE = 60_000
CRIT = (cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_MAX_ITER, 20, 0.5)


def _fit(sample: np.ndarray, k: int):
    k = min(k, len(sample))
    comp, _, centers = cv2.kmeans(sample, k, None, CRIT, 3, cv2.KMEANS_PP_CENTERS)
    return comp, centers


def _auto_centers(sample: np.ndarray, max_n: int) -> np.ndarray:
    """Smallest k where adding one more color barely helps (elbow)."""
    prev = _fit(sample, 1)
    for k in range(1, max_n):
        nxt = _fit(sample, k + 1)
        # stop when the error is already tiny (rms dE < 2) or the drop is under 15%
        if prev[0] / len(sample) < 4.0 or prev[0] - nxt[0] < 0.15 * prev[0]:
            return prev[1]
        prev = nxt
    return prev[1]


def quantize(img: np.ndarray, n: int | None = None, max_n: int = 16, merge_de: float = 16.0):
    """Cut an RGBA image to a few flat colors (k-means in Lab).

    n=None picks the count automatically. Returns (RGBA image, [(hex, share), ...]).
    """
    cv2.setRNGSeed(0)  # kmeans picks random starts; fixed seed keeps results repeatable
    h, w = img.shape[:2]
    lab = cv2.cvtColor(img[..., :3].astype(np.float32) / 255, cv2.COLOR_RGB2LAB).reshape(-1, 3)
    solid = img[..., 3].reshape(-1) >= 128
    px = lab[solid]
    if len(px) == 0:
        return img, []
    if len(px) > SAMPLE:
        px = px[np.random.default_rng(0).choice(len(px), SAMPLE, replace=False)]
    sample = np.ascontiguousarray(px, np.float32)
    centers = _fit(sample, n)[1] if n else _auto_centers(sample, max_n)

    keep = []  # drop centers that are almost the same color as one already kept
    for c in centers:
        if all(np.linalg.norm(c - k) >= merge_de for k in keep):
            keep.append(c)
    keep = np.array(keep, np.float32)

    idx = np.empty(len(lab), np.int32)
    for i in range(0, len(lab), 1_000_000):  # chunked: 16 MP x k floats is too big at once
        d = np.linalg.norm(lab[i:i + 1_000_000, None, :] - keep[None], axis=2)
        idx[i:i + 1_000_000] = d.argmin(axis=1)

    rgb = cv2.cvtColor(keep[None], cv2.COLOR_LAB2RGB)[0]
    rgb = (rgb * 255).round().clip(0, 255).astype(np.uint8)
    out = img.copy()
    out[..., :3] = rgb[idx].reshape(h, w, 3)
    share = np.bincount(idx[solid], minlength=len(keep)) / solid.sum()
    palette = [(f"#{c[0]:02X}{c[1]:02X}{c[2]:02X}", round(float(s), 4)) for c, s in zip(rgb, share)]
    return out, sorted(palette, key=lambda p: -p[1])
