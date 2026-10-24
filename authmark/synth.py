"""Procedural test image generator (so the project runs with no external data)."""
import numpy as np
from PIL import Image


def make_image(size=512, seed=0):
    rng = np.random.default_rng(seed)
    yy, xx = np.mgrid[0:size, 0:size] / size
    base = np.stack([0.5 + 0.4 * np.sin(6 * xx + seed), 0.5 + 0.4 * np.sin(5 * yy + 2 * xx),
                     0.5 + 0.4 * np.cos(7 * (xx + yy))], -1)
    for _ in range(25):
        cx, cy, r = rng.random() * size, rng.random() * size, rng.integers(15, 70)
        col = rng.random(3)
        m = (np.arange(size)[None, :] - cx) ** 2 + (np.arange(size)[:, None] - cy) ** 2 < r * r
        base[m] = 0.6 * base[m] + 0.4 * col
    base += rng.normal(0, 0.02, base.shape)
    return Image.fromarray((np.clip(base, 0, 1) * 255).astype(np.uint8))
