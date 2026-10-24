import numpy as np
from scipy.ndimage import uniform_filter


def psnr(a, b):
    a, b = np.asarray(a, float), np.asarray(b, float)
    mse = np.mean((a - b) ** 2)
    return float("inf") if mse == 0 else 10 * np.log10(255 ** 2 / mse)


def ssim(a, b):
    """Mean SSIM on luminance (uniform 7x7 window)."""
    def lum(x):
        x = np.asarray(x, float)
        return x if x.ndim == 2 else x @ [0.299, 0.587, 0.114]
    a, b = lum(a), lum(b)
    c1, c2 = (0.01 * 255) ** 2, (0.03 * 255) ** 2
    mu_a, mu_b = uniform_filter(a, 7), uniform_filter(b, 7)
    va = uniform_filter(a * a, 7) - mu_a ** 2
    vb = uniform_filter(b * b, 7) - mu_b ** 2
    cov = uniform_filter(a * b, 7) - mu_a * mu_b
    s = ((2 * mu_a * mu_b + c1) * (2 * cov + c2)) / ((mu_a ** 2 + mu_b ** 2 + c1) * (va + vb + c2))
    return float(s.mean())
