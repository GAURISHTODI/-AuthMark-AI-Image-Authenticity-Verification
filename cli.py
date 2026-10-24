"""AuthMark command line.

  python cli.py embed  in.png out.png --key "pass" --creator 42
  python cli.py verify out.png --key "pass" [--report report.png]
"""
import argparse
import os
import sys

from PIL import Image

from authmark import derive_key, embed, verify
from authmark.metrics import psnr, ssim
from authmark.report import render_report, summary_text


def main(argv=None):
    ap = argparse.ArgumentParser(description="AI image authenticity via invisible watermarking")
    sub = ap.add_subparsers(dest="cmd", required=True)
    e = sub.add_parser("embed")
    e.add_argument("input"); e.add_argument("output")
    e.add_argument("--key", required=True); e.add_argument("--creator", type=int, default=1)
    v = sub.add_parser("verify")
    v.add_argument("input"); v.add_argument("--key", required=True)
    v.add_argument("--report", help="save a visual report PNG")
    a = ap.parse_args(argv)
    key = derive_key(a.key)

    if a.cmd == "embed":
        src = Image.open(a.input).convert("RGB")
        out = embed(src, key, a.creator)
        if not a.output.lower().endswith(".png"):
            print("warning: use a lossless format (PNG) for the watermarked output", file=sys.stderr)
        out.save(a.output)
        print(f"watermarked -> {a.output}  PSNR={psnr(src, out):.2f} dB  SSIM={ssim(src, out):.4f}")
        return 0

    img = Image.open(a.input).convert("RGB")
    r = verify(img, key)
    print(summary_text(img, r, os.path.basename(a.input)))
    if a.report:
        render_report(img, r, os.path.basename(a.input)).save(a.report)
        print(f"\nreport image -> {a.report}")
    return 0 if r.is_authentic else 1


if __name__ == "__main__":
    sys.exit(main())
