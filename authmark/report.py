"""Verification report: summary tables, tamper overlay and a printable report page."""
import datetime as dt
import hashlib
import io
import os

import numpy as np
from PIL import Image, ImageDraw, ImageFont

VERDICT_TEXT = {
    "AUTHENTIC": "Valid signature found; no tampering detected.",
    "TAMPERED": "Valid signature found, but parts of the image were altered.",
    "NOT_VERIFIED": "No valid watermark for this key (unsigned, wrong key, or destroyed).",
}
VERDICT_COLOR = {"AUTHENTIC": (34, 197, 94), "TAMPERED": (239, 68, 68), "NOT_VERIFIED": (245, 158, 11)}


def overlay(img: Image.Image, result) -> Image.Image:
    a = np.asarray(img.convert("RGB"), float)
    m = result.tamper_mask
    if m is not None and m.any():
        a[m] = 0.55 * a[m] + 0.45 * np.array([255, 0, 0])
    out = Image.fromarray(a.astype(np.uint8))
    d = ImageDraw.Draw(out)
    for box in result.regions:
        d.rectangle(box, outline=(255, 255, 0), width=3)
    return out


def image_sha256(img: Image.Image) -> str:
    return hashlib.sha256(img.convert("RGB").tobytes()).hexdigest()


def rating(result) -> str:
    if not result.signature_valid:
        return "None"
    if result.verdict == "AUTHENTIC" and result.block_agreement > 0.95 and result.bit_confidence > 0.8:
        return "High"
    if result.verdict == "AUTHENTIC":
        return "Medium"
    return "Low (edited)"


def summary_sections(img: Image.Image, result, filename: str = "uploaded image"):
    """[(section title, [(label, value), ...]), ...] used by CLI, web UI and report image."""
    st = result.stats or {}
    now = dt.datetime.now(dt.timezone.utc)
    p = result.payload
    signed = (dt.datetime.fromtimestamp(p.timestamp, dt.timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
              if p else "n/a")
    ok = result.signature_valid
    return [
        ("Verdict", [
            ("Result", result.verdict.replace("_", " ")),
            ("Meaning", VERDICT_TEXT[result.verdict]),
            ("Trust rating", rating(result)),
        ]),
        ("Watermark payload", [
            ("Creator ID", str(p.creator_id) if p else "n/a"),
            ("Signed at", signed),
            ("Signature (HMAC-SHA256)", "VALID" if ok else "INVALID / not found"),
            ("Payload size", "96 bits (32 ID + 32 time + 32 tag)"),
        ]),
        ("Extraction quality", [
            ("Block agreement", f"{result.block_agreement:.1%}"),
            ("Bit confidence", f"{result.bit_confidence:.2f}  (1.00 = perfect)"),
            ("Weakest bit confidence", f"{st.get('min_bit_confidence', 0):.2f}"),
            ("Weak bits (< 0.30)", f"{st.get('weak_bits', 0)} of 96"),
            ("Copies per bit (redundancy)", f"{st.get('copies_per_bit', 0):.1f}"),
            ("Gain correction applied", f"x{st.get('gain', 1.0):.2f}"),
        ]),
        ("Tamper analysis", [
            ("Blocks analysed", f"{st.get('blocks_analysed', 0):,}"),
            ("Blocks disagreeing", f"{st.get('blocks_disagreeing', 0):,}"),
            ("Blocks flagged as tampered", f"{st.get('blocks_flagged', 0):,}"),
            ("Tampered area", f"{result.tamper_ratio:.1%}  (threshold 2%)"),
            ("Suspicious regions", str(len(result.regions))),
        ] + [(f"  Region {i + 1} (x0,y0,x1,y1)", str(b)) for i, b in enumerate(result.regions[:4])]),
        ("Image and method", [
            ("File", filename),
            ("Resolution", f"{img.width} x {img.height} px"),
            ("Image SHA-256", image_sha256(img)[:32] + "..."),
            ("Method", f"Haar DWT + 8x8 DCT + QIM (delta {st.get('delta', 28):g})"),
            ("Verified on", now.strftime("%Y-%m-%d %H:%M:%S UTC")),
        ]),
    ]


def summary_text(img, result, filename="uploaded image") -> str:
    lines = ["=" * 60, "AUTHMARK VERIFICATION REPORT", "=" * 60]
    for title, rows in summary_sections(img, result, filename):
        lines += ["", title.upper(), "-" * len(title)]
        w = max(len(k) for k, _ in rows)
        lines += [f"{k.ljust(w)} : {v}" for k, v in rows]
    return "\n".join(lines)


def _font(size, bold=False):
    names = ["arialbd.ttf", "calibrib.ttf", "DejaVuSans-Bold.ttf"] if bold else ["arial.ttf", "calibri.ttf", "DejaVuSans.ttf"]
    for n in names:
        try:
            return ImageFont.truetype(n, size)
        except OSError:
            continue
    return ImageFont.load_default()


def render_report(img: Image.Image, result, filename: str = "uploaded image") -> Image.Image:
    """One-page report: banner, input + tamper map, and the full summary tables."""
    W, M = 1700, 40
    bg, card, text, muted, teal = (11, 31, 58), (22, 50, 88), (255, 255, 255), (184, 199, 220), (20, 184, 166)
    secs = summary_sections(img, result, filename)
    col_w = (W - 3 * M) // 2
    thumb = (W - 3 * M) // 2
    th = int(thumb * img.height / img.width)
    left = [secs[0], secs[1], secs[4]]
    right = [secs[2], secs[3]]
    row_h, head_h, pad = 34, 46, 14

    def col_height(sections):
        return sum(head_h + len(rows) * row_h + pad * 2 + 18 for _, rows in sections)

    H = M + 110 + 30 + th + 50 + max(col_height(left), col_height(right)) + 70
    canvas = Image.new("RGB", (W, H), bg)
    d = ImageDraw.Draw(canvas)
    vc = VERDICT_COLOR[result.verdict]
    d.rounded_rectangle((M, M, W - M, M + 110), 16, fill=vc)
    d.text((M + 28, M + 14), "AUTHMARK VERIFICATION REPORT", font=_font(22, True), fill=(11, 31, 58))
    d.text((M + 28, M + 46), result.verdict.replace("_", " "), font=_font(46, True), fill=(11, 31, 58))
    d.text((W - M - 28, M + 62), VERDICT_TEXT[result.verdict], font=_font(20), fill=(11, 31, 58), anchor="rm")

    y = M + 110 + 30
    canvas.paste(img.convert("RGB").resize((thumb, th)), (M, y))
    canvas.paste(overlay(img, result).resize((thumb, th)), (2 * M + thumb, y))
    d.text((M, y + th + 10), "Input image", font=_font(20), fill=muted)
    d.text((2 * M + thumb, y + th + 10), "Tamper map (red = altered, yellow box = region)", font=_font(20), fill=muted)
    top = y + th + 50

    def draw_col(sections, x):
        yy = top
        for title, rows in sections:
            hh = head_h + len(rows) * row_h + pad * 2 + 6
            d.rounded_rectangle((x, yy, x + col_w, yy + hh), 14, fill=card)
            d.text((x + 22, yy + 14), title.upper(), font=_font(22, True), fill=teal)
            ry = yy + head_h + pad - 4
            for k, v in rows:
                d.text((x + 22, ry), k, font=_font(19), fill=muted)
                d.text((x + col_w - 22, ry), v, font=_font(19, True), fill=text, anchor="ra")
                ry += row_h
            yy += hh + 18

    draw_col(left, M)
    draw_col(right, 2 * M + col_w)
    d.text((W // 2, H - 34), "Generated by AuthMark  |  DWT + DCT + QIM invisible watermark with HMAC-SHA256 signature",
           font=_font(17), fill=muted, anchor="mm")
    return canvas
