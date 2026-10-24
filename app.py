"""Streamlit UI:  streamlit run app.py"""
import io
import os
import time

import streamlit as st
from PIL import Image

from authmark import derive_key, embed, verify
from authmark.metrics import psnr, ssim
from authmark.report import overlay, render_report, summary_sections, summary_text

st.set_page_config(page_title="AuthMark", page_icon="🛡️", layout="wide")
st.title("🛡️ AuthMark — AI Image Authenticity Verification")
st.caption("Invisible DWT-DCT-QIM watermark with an HMAC-signed payload and tamper localisation.")

with st.sidebar:
    passphrase = st.text_input("Secret key", type="password", value="demo-key")
    st.info("The same secret key is needed to sign and to verify.")
    save_dir = st.text_input("Save folder (D drive)", value=r"D:\Code\Watermarking\outputs")
    st.caption("Use the 'Save to folder' buttons to write files here instead of the browser's Downloads folder (C:).")


def save_file(name, data):
    """Write bytes/text to the chosen folder; returns the full path."""
    os.makedirs(save_dir, exist_ok=True)
    path = os.path.join(save_dir, f"{time.strftime('%Y%m%d_%H%M%S')}_{name}")
    with open(path, "wb") as fh:
        fh.write(data if isinstance(data, bytes) else data.encode("utf8"))
    return path
key = derive_key(passphrase)

sign_tab, verify_tab = st.tabs(["1 · Sign (embed)", "2 · Verify"])

with sign_tab:
    up = st.file_uploader("AI-generated image", type=["png", "jpg", "jpeg", "webp"], key="u1")
    cid = st.number_input("Creator / model ID", 0, 2**32 - 1, 1)
    if up:
        src = Image.open(up).convert("RGB")
        try:
            out = embed(src, key, int(cid))
        except ValueError as e:
            st.error(str(e)); st.stop()
        c1, c2 = st.columns(2)
        c1.image(src, caption="Original"); c2.image(out, caption="Watermarked (invisible)")
        st.metric("PSNR", f"{psnr(src, out):.2f} dB"); st.metric("SSIM", f"{ssim(src, out):.4f}")
        buf = io.BytesIO(); out.save(buf, "PNG")
        st.download_button("Download watermarked PNG", buf.getvalue(), "signed.png", "image/png")
        if st.button("Save to folder", key="save_signed"):
            st.success(f"Saved: {save_file('signed.png', buf.getvalue())}")
        st.warning("Save/share as PNG. Lossy re-encoding is tolerated, but PNG is safest.")

with verify_tab:
    up2 = st.file_uploader("Image to verify", type=["png", "jpg", "jpeg", "webp"], key="u2")
    if up2:
        img = Image.open(up2).convert("RGB")
        try:
            r = verify(img, key)
        except ValueError as e:
            st.error(str(e)); st.stop()
        if r.verdict == "AUTHENTIC":
            st.success("✅ AUTHENTIC — valid signature, no tampering detected")
        elif r.verdict == "TAMPERED":
            st.error(f"⚠️ TAMPERED — valid signature but {r.tamper_ratio:.1%} of the image was altered")
        else:
            st.warning("❓ NOT VERIFIED — no valid watermark for this key (unsigned, wrong key, "
                       "or destroyed by heavy blur/crop)")
        c1, c2 = st.columns(2)
        c1.image(img, caption="Input"); c2.image(overlay(img, r), caption="Tamper map")
        st.subheader("Verification report")
        sections = summary_sections(img, r, up2.name)
        ca, cb = st.columns(2)
        for i, (title, rows) in enumerate(sections):
            with (ca if i in (0, 1, 4) else cb):
                st.markdown(f"**{title}**")
                st.table({"Parameter": [k.strip() for k, _ in rows], "Value": [v for _, v in rows]})
        buf = io.BytesIO(); render_report(img, r, up2.name).save(buf, "PNG")
        d1, d2 = st.columns(2)
        d1.download_button("Download report (PNG)", buf.getvalue(), "authmark_report.png", "image/png")
        d2.download_button("Download report (TXT)", summary_text(img, r, up2.name), "authmark_report.txt")
        if st.button("Save report + tamper map to folder", key="save_report"):
            base = os.path.splitext(up2.name)[0]
            buf2 = io.BytesIO(); overlay(img, r).save(buf2, "PNG")
            paths = [save_file(f"{base}_report.png", buf.getvalue()),
                     save_file(f"{base}_report.txt", summary_text(img, r, up2.name)),
                     save_file(f"{base}_tamper_map.png", buf2.getvalue())]
            st.success("Saved: " + "  |  ".join(paths))
