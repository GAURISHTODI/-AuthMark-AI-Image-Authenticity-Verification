"""Benchmark: imperceptibility + robustness + tamper detection. Writes results/ files."""
import os

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

from authmark import derive_key, embed, verify
from authmark import attacks as A
from authmark.metrics import psnr, ssim
from authmark.synth import make_image

N_IMAGES = 8
ATTACKS = {
    "none": lambda x: x,
    "JPEG q=90": lambda x: A.jpeg(x, 90), "JPEG q=75": lambda x: A.jpeg(x, 75),
    "JPEG q=50": lambda x: A.jpeg(x, 50),
    "Gaussian noise s=3": lambda x: A.gaussian_noise(x, 3), "Gaussian noise s=8": lambda x: A.gaussian_noise(x, 8),
    "Brightness x1.1": lambda x: A.brightness(x, 1.1),
    "Rescale 0.5 round-trip": A.rescale_roundtrip,
    "Blur r=0.6": lambda x: A.blur(x, 0.6),
    "Blur r=1.0": lambda x: A.blur(x, 1.0),
    "Crop 90% (desync)": A.screenshot_crop,
}
TAMPERS = {"Patch 9% area": lambda x: A.paste_patch(x, (0.3, 0.3, 0.6, 0.6)),
           "Patch 4% area": lambda x: A.paste_patch(x, (0.1, 0.5, 0.3, 0.7))}


def main():
    key = derive_key("evaluation-key")
    os.makedirs("results", exist_ok=True)
    imgs = [make_image(512, s) for s in range(N_IMAGES)]
    wms = [embed(im, key, 1000 + i) for i, im in enumerate(imgs)]
    lines = ["# AuthMark evaluation", "",
             f"Images: {N_IMAGES} synthetic 512x512", "",
             f"Imperceptibility: mean PSNR = {sum(psnr(a, b) for a, b in zip(imgs, wms)) / N_IMAGES:.2f} dB, "
             f"mean SSIM = {sum(ssim(a, b) for a, b in zip(imgs, wms)) / N_IMAGES:.4f}", "",
             "## Robustness (watermark should still verify as AUTHENTIC)", "",
             "| Attack | Signature valid | Verdict AUTHENTIC | Mean block agreement |", "|---|---|---|---|"]
    names, agr = [], []
    for name, f in ATTACKS.items():
        rs = [verify(f(w), key) for w in wms]
        sig = sum(r.signature_valid for r in rs); au = sum(r.is_authentic for r in rs)
        ba = sum(r.block_agreement for r in rs) / N_IMAGES
        lines.append(f"| {name} | {sig}/{N_IMAGES} | {au}/{N_IMAGES} | {ba:.1%} |")
        names.append(name); agr.append(ba)
    lines += ["", "## Tamper detection (should be flagged TAMPERED)", "",
              "| Edit | Detected | Mean flagged area |", "|---|---|---|"]
    for name, f in TAMPERS.items():
        rs = [verify(f(w), key) for w in wms]
        lines.append(f"| {name} | {sum(r.verdict == 'TAMPERED' for r in rs)}/{N_IMAGES} | "
                     f"{sum(r.tamper_ratio for r in rs) / N_IMAGES:.1%} |")
    fa = [verify(im, key) for im in imgs] + [verify(w, derive_key('wrong')) for w in wms]
    lines += ["", "## False accepts",
              f"Un-watermarked images and wrong-key checks accepted as AUTHENTIC: "
              f"{sum(r.is_authentic for r in fa)}/{len(fa)}"]
    with open("results/report.md", "w") as fh:
        fh.write("\n".join(lines) + "\n")

    plt.figure(figsize=(9, 4.5))
    plt.barh(names[::-1], [a * 100 for a in agr[::-1]], color="#3b82f6")
    plt.axvline(50, color="gray", ls="--", label="chance")
    plt.xlabel("Block agreement with embedded payload (%)"); plt.legend(); plt.tight_layout()
    plt.savefig("results/robustness.png", dpi=130)
    print("\n".join(lines))


if __name__ == "__main__":
    main()
