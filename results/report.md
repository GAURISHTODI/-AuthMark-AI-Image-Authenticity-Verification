# AuthMark evaluation

Images: 8 synthetic 512x512

Imperceptibility: mean PSNR = 42.30 dB, mean SSIM = 0.9828

## Robustness (watermark should still verify as AUTHENTIC)

| Attack | Signature valid | Verdict AUTHENTIC | Mean block agreement |
|---|---|---|---|
| none | 8/8 | 8/8 | 100.0% |
| JPEG q=90 | 8/8 | 8/8 | 100.0% |
| JPEG q=75 | 8/8 | 8/8 | 100.0% |
| JPEG q=50 | 8/8 | 8/8 | 99.5% |
| Gaussian noise s=3 | 8/8 | 8/8 | 100.0% |
| Gaussian noise s=8 | 8/8 | 8/8 | 98.7% |
| Brightness x1.1 | 8/8 | 8/8 | 100.0% |
| Rescale 0.5 round-trip | 8/8 | 8/8 | 100.0% |
| Blur r=0.6 | 8/8 | 8/8 | 100.0% |
| Blur r=1.0 | 0/8 | 0/8 | 99.0% |
| Crop 90% (desync) | 0/8 | 0/8 | 66.3% |

## Tamper detection (should be flagged TAMPERED)

| Edit | Detected | Mean flagged area |
|---|---|---|
| Patch 9% area | 8/8 | 6.2% |
| Patch 4% area | 8/8 | 2.8% |

## False accepts
Un-watermarked images and wrong-key checks accepted as AUTHENTIC: 0/16
