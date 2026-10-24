# AuthMark — AI Image Authenticity Verification via Invisible Digital Watermarking

End-to-end system: **sign** an AI-generated image with an invisible, cryptographically signed watermark, then later **verify** whether an image is authentic, unsigned, or tampered — and *where*.

## How it works

```
Sign:   RGB -> YCbCr -> Y -> Haar DWT (LL) -> 8x8 block DCT -> QIM embed (6 mid-freq coeffs/block) -> RGB
Payload (96 bits): creator_id(32) | timestamp(32) | HMAC-SHA256(secret, id||ts)[:32]
Verify: reverse transform -> gain search -> soft majority vote per bit -> check HMAC -> per-block consensus check
```

- **Invisible**: marks only mid-frequency LL-band DCT coefficients of luminance (PSNR ≈ 42 dB, SSIM ≈ 0.98).
- **Authentic**: payload is HMAC-signed; without the secret key a valid mark cannot be forged.
- **Robust**: payload bits are tiled over the whole image through a key-seeded permutation (~8 votes × 6 coefficients per bit).
- **Tamper localisation**: the payload is redundant, so blocks that disagree with the consensus pinpoint edited regions (inpainting, object swap) → heat-map + bounding boxes.
- **Verdicts**: `AUTHENTIC` (valid signature, no tamper) · `TAMPERED` (valid signature, localized damage) · `NOT_VERIFIED` (no valid mark for this key).

## Run

```bash
pip install -r requirements.txt
python -m pytest -q                       # 11 tests
python evaluate.py                        # writes results/report.md + robustness.png
python -m streamlit run app.py                      # web UI (sign + verify tabs)

python cli.py embed samples/ai_image.png samples/signed.png --key mykey --creator 7
python cli.py verify samples/signed.png --key mykey
python cli.py verify samples/tampered.png --key mykey --report results/tamper_report.png
```

## Layout

| File | Purpose |
|---|---|
| `authmark/core.py` | embed / verify engine, payload + HMAC, tamper localisation |
| `authmark/attacks.py` | JPEG, noise, blur, brightness, rescale, crop, patch-paste |
| `authmark/metrics.py` | PSNR, SSIM |
| `authmark/report.py` | tamper overlay / report image |
| `cli.py`, `app.py` | command line and Streamlit UI |
| `evaluate.py`, `tests/` | benchmark and unit tests |

## Measured results (8 synthetic 512×512 images, see `results/report.md`)

- PSNR 42.3 dB, SSIM 0.982
- Verifies as AUTHENTIC after JPEG q=50–90, Gaussian noise σ≤8, brightness ×1.1, 50 % down/up-scale, blur r=0.6 (8/8 each)
- Localized edits flagged TAMPERED: 8/8 (9 % area), 7/8 (4 % area)
- 0/16 false accepts (unwatermarked images, wrong keys)

## Known limitations (state these in your report)

- Not robust to **cropping / geometric transforms** (loses block-grid sync) or **strong blur** (r ≥ 1) — would need a synchronization template or log-polar/SIFT-based registration.
- Strong brightness gain with clipping (×1.2) damages the mark; gain up to ~±25 % without clipping is handled by a gain search.
- Verification needs the **secret key** (symmetric HMAC). A public-verifiable variant would use an asymmetric signature (e.g. Ed25519), requiring a longer payload.
- Evaluated on synthetic images; try real photos / Stable Diffusion outputs — drop them into `samples/`. A regenerative attack by a diffusion model on the whole image will remove any pixel-domain watermark.
- Save signed images as PNG; the mark survives later JPEG, but embedding is done on 8-bit pixels.

## Ideas for extension
Ed25519 signatures, learned (HiDDeN-style) encoder/decoder for comparison, DWT level-2 for more blur robustness, synchronization pattern for crop resistance, batch API / FastAPI service.

## Documentation
- `AuthMark_Project_Report.docx` / `.pdf`: full project report
- `AuthMark_Presentation.pptx`: presentation deck
- `diagrams/`: architecture, embedding and verification diagrams (`diagrams/bw/` = black and white versions)
- The Verify tab and `cli.py verify --report` produce a full verification report (payload, extraction quality, tamper analysis).
