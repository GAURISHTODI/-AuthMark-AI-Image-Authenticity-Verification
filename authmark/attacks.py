"""Common image processing attacks / benign transformations used for evaluation."""
import io

import numpy as np
from PIL import Image, ImageFilter


def jpeg(img, q=75):
    buf = io.BytesIO()
    img.save(buf, "JPEG", quality=q)
    buf.seek(0)
    return Image.open(buf).convert("RGB")


def gaussian_noise(img, sigma=5, seed=0):
    a = np.asarray(img, float) + np.random.default_rng(seed).normal(0, sigma, (img.height, img.width, 3))
    return Image.fromarray(np.clip(a, 0, 255).astype(np.uint8))


def blur(img, radius=1.0):
    return img.filter(ImageFilter.GaussianBlur(radius))


def brightness(img, gain=1.1):
    return Image.fromarray(np.clip(np.asarray(img, float) * gain, 0, 255).astype(np.uint8))


def rescale_roundtrip(img, scale=0.5):
    w, h = img.size
    small = img.resize((max(1, int(w * scale)), max(1, int(h * scale))), Image.BICUBIC)
    return small.resize((w, h), Image.BICUBIC)


def paste_patch(img, box=(0.3, 0.3, 0.6, 0.6), seed=1):
    """Simulate localized AI inpainting / object replacement with a synthetic patch."""
    w, h = img.size
    x0, y0, x1, y1 = int(box[0] * w), int(box[1] * h), int(box[2] * w), int(box[3] * h)
    a = np.asarray(img).copy()
    rng = np.random.default_rng(seed)
    base = rng.integers(60, 200, 3)
    patch = base + rng.normal(0, 12, (y1 - y0, x1 - x0, 3))
    a[y0:y1, x0:x1] = np.clip(patch, 0, 255).astype(np.uint8)
    return Image.fromarray(a)


def screenshot_crop(img, frac=0.9):
    w, h = img.size
    return img.crop((0, 0, int(w * frac), int(h * frac)))
