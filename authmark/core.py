"""Core invisible watermarking engine.

Pipeline (embed):
    RGB -> YCbCr -> Y channel -> 1-level Haar DWT -> LL band
        -> 8x8 block DCT -> QIM-embed one payload bit in two mid-frequency
        coefficients of every block -> inverse DCT/DWT -> RGB.

The payload is a signed 96-bit record:
    creator_id (32) | unix timestamp (32) | HMAC-SHA256(key, id||ts)[:32]
Every bit is spread over many blocks via a key-seeded permutation, so decoding
uses soft majority voting. Because the same payload is tiled over the whole
image, blocks that disagree with the consensus reveal *localized tampering*
(inpainting, object replacement, AI regeneration of a region).
"""
from __future__ import annotations

import hashlib
import hmac
import struct
import time
from dataclasses import dataclass, field

import numpy as np
from PIL import Image
from scipy.fft import dctn, idctn
from scipy.ndimage import uniform_filter, label

PAYLOAD_BITS = 96
BLOCK = 8                      # DCT block size (in LL band) -> 16x16 image px
COEFFS = ((3, 4), (4, 3), (2, 5), (5, 2), (3, 3), (2, 4))
DEFAULT_DELTA = 28.0           # QIM step: larger = more robust, less invisible
GAINS = np.round(np.arange(0.75, 1.3001, 0.01), 2)   # tolerated global gain range
MIN_COPIES = 4                 # minimum redundancy per payload bit


# ----------------------------------------------------------------- payload
@dataclass
class Payload:
    creator_id: int
    timestamp: int

    def mac(self, key: bytes) -> bytes:
        msg = struct.pack(">II", self.creator_id, self.timestamp)
        return hmac.new(key, msg, hashlib.sha256).digest()[:4]

    def to_bits(self, key: bytes) -> np.ndarray:
        raw = struct.pack(">II", self.creator_id, self.timestamp) + self.mac(key)
        return np.unpackbits(np.frombuffer(raw, dtype=np.uint8))

    @staticmethod
    def from_bits(bits: np.ndarray, key: bytes) -> tuple["Payload", bool]:
        raw = np.packbits(bits.astype(np.uint8)).tobytes()
        cid, ts = struct.unpack(">II", raw[:8])
        p = Payload(cid, ts)
        return p, hmac.compare_digest(p.mac(key), raw[8:12])


# ------------------------------------------------------------- transforms
def _haar(x):
    a, b, c, d = x[0::2, 0::2], x[0::2, 1::2], x[1::2, 0::2], x[1::2, 1::2]
    return ((a + b + c + d) / 2, (a - b + c - d) / 2,
            (a + b - c - d) / 2, (a - b - c + d) / 2)


def _ihaar(ll, h, v, d):
    out = np.empty((ll.shape[0] * 2, ll.shape[1] * 2), dtype=ll.dtype)
    out[0::2, 0::2] = (ll + h + v + d) / 2
    out[0::2, 1::2] = (ll - h + v - d) / 2
    out[1::2, 0::2] = (ll + h - v - d) / 2
    out[1::2, 1::2] = (ll - h - v + d) / 2
    return out


def _to_blocks(m):
    h, w = m.shape
    return m.reshape(h // BLOCK, BLOCK, w // BLOCK, BLOCK).transpose(0, 2, 1, 3)


def _from_blocks(b):
    nby, nbx = b.shape[:2]
    return b.transpose(0, 2, 1, 3).reshape(nby * BLOCK, nbx * BLOCK)


def _pad16(y):
    h, w = y.shape
    ph, pw = (-h) % (2 * BLOCK), (-w) % (2 * BLOCK)
    return np.pad(y, ((0, ph), (0, pw)), mode="reflect") if ph or pw else y


def _layout(shape_hw, key: bytes):
    """Block grid, key-seeded bit assignment and mask of fully-inside blocks."""
    h, w = shape_hw
    nby, nbx = -(-h // (2 * BLOCK)), -(-w // (2 * BLOCK))
    seed = int.from_bytes(hashlib.sha256(b"layout" + key).digest()[:8], "big")
    perm = np.random.default_rng(seed).permutation(nby * nbx)
    bit_idx = (perm % PAYLOAD_BITS).reshape(nby, nbx)
    valid = np.zeros((nby, nbx), bool)
    valid[: h // (2 * BLOCK), : w // (2 * BLOCK)] = True
    return bit_idx, valid


# -------------------------------------------------------------------- QIM
def _qim_embed(c, bit, delta):
    off = bit * delta / 2
    return np.round((c - off) / delta) * delta + off


def _qim_soft(c, delta):
    """Positive => bit 1, negative => bit 0; magnitude in [-1, 1]."""
    d0 = np.abs(c - np.round(c / delta) * delta)
    d1 = np.abs(c - (np.round((c - delta / 2) / delta) * delta + delta / 2))
    return (d0 - d1) / (delta / 2)


# ------------------------------------------------------------------ embed
def embed(img: Image.Image, key: bytes, creator_id: int, timestamp: int | None = None,
          delta: float = DEFAULT_DELTA) -> Image.Image:
    img = img.convert("RGB")
    w, h = img.size
    bit_idx, valid = _layout((h, w), key)
    if valid.sum() < PAYLOAD_BITS * MIN_COPIES:
        raise ValueError(f"Image too small ({w}x{h}); need roughly >= 256x256 pixels.")

    payload = Payload(creator_id, int(timestamp if timestamp is not None else time.time()))
    bits = payload.to_bits(key)

    ycc = np.asarray(img.convert("YCbCr"), dtype=np.float64)
    y = _pad16(ycc[..., 0])
    ll, hh, vv, dd = _haar(y)
    blocks = dctn(_to_blocks(ll), axes=(2, 3), norm="ortho")
    b = bits[bit_idx]
    for (u, v) in COEFFS:
        blocks[:, :, u, v] = _qim_embed(blocks[:, :, u, v], b, delta)
    ll2 = _from_blocks(idctn(blocks, axes=(2, 3), norm="ortho"))
    y2 = _ihaar(ll2, hh, vv, dd)[:h, :w]

    out = ycc.copy()
    out[..., 0] = y2
    out = np.clip(np.round(out), 0, 255).astype(np.uint8)
    return Image.fromarray(out, "YCbCr").convert("RGB")


# ----------------------------------------------------------------- verify
@dataclass
class VerifyResult:
    verdict: str                      # AUTHENTIC | TAMPERED | NOT_VERIFIED
    signature_valid: bool
    payload: Payload | None
    bit_confidence: float             # mean |vote| strength, 0..1
    block_agreement: float            # fraction of blocks agreeing w/ consensus
    tamper_ratio: float               # fraction of image flagged as tampered
    tamper_mask: np.ndarray = field(repr=False, default=None)  # bool, image-sized
    regions: list = field(default_factory=list)  # [(x0,y0,x1,y1)]
    stats: dict = field(default_factory=dict)    # extra diagnostics for the report

    @property
    def is_authentic(self):
        return self.verdict == "AUTHENTIC"


def verify(img: Image.Image, key: bytes, delta: float = DEFAULT_DELTA,
           tamper_threshold: float = 0.02) -> VerifyResult:
    img = img.convert("RGB")
    w, h = img.size
    bit_idx, valid = _layout((h, w), key)
    if valid.sum() < PAYLOAD_BITS * MIN_COPIES:
        raise ValueError("Image too small to verify.")

    y = _pad16(np.asarray(img.convert("YCbCr"), dtype=np.float64)[..., 0])
    ll, *_ = _haar(y)
    blocks = dctn(_to_blocks(ll), axes=(2, 3), norm="ortho")
    # QIM is sensitive to amplitude scaling (contrast/brightness gain): search a
    # small set of gains and keep the one that best fits the quantisation lattice.
    best = None
    for g in GAINS:
        sf = np.mean([_qim_soft(blocks[:, :, u, v] / g, delta) for (u, v) in COEFFS], axis=0)
        fit = np.abs(sf[valid]).mean()
        if best is None or fit > best[0]:
            best = (fit, sf, float(g))
    soft, gain = best[1], best[2]

    votes = np.zeros(PAYLOAD_BITS)
    counts = np.zeros(PAYLOAD_BITS)
    np.add.at(votes, bit_idx[valid], soft[valid])
    np.add.at(counts, bit_idx[valid], 1)
    avg = votes / np.maximum(counts, 1)
    bits = (avg > 0).astype(np.uint8)
    payload, sig_ok = Payload.from_bits(bits, key)

    agree = (soft > 0) == bits[bit_idx].astype(bool)
    block_agreement = float(agree[valid].mean())
    conf = float(np.abs(avg).mean())
    stats = {
        "width": w, "height": h, "delta": delta,
        "gain": gain,
        "blocks_analysed": int(valid.sum()),
        "copies_per_bit": float(counts.mean()),
        "min_bit_confidence": float(np.abs(avg).min()),
        "weak_bits": int((np.abs(avg) < 0.3).sum()),
        "blocks_disagreeing": int((~agree & valid).sum()),
        "blocks_flagged": 0,
    }

    if not sig_ok:
        return VerifyResult("NOT_VERIFIED", False, None, conf, block_agreement, 0.0,
                            np.zeros((h, w), bool), stats=stats)

    # Tamper localisation: windowed disagreement of blocks vs. consensus.
    dis = (~agree & valid).astype(float)
    wgt = valid.astype(float)
    num = uniform_filter(dis, 3, mode="constant")
    den = np.maximum(uniform_filter(wgt, 3, mode="constant"), 1e-6)
    local = (num / den) * valid
    bmask = local > 0.3
    lab, n = label(bmask)
    for i in range(1, n + 1):                 # drop isolated specks
        if (lab == i).sum() < 2:
            bmask[lab == i] = False
    s = 2 * BLOCK
    mask = np.kron(bmask, np.ones((s, s), bool))[:h, :w]
    ratio = float(mask.mean())

    lab, n = label(bmask)
    regions = []
    for i in range(1, n + 1):
        ys, xs = np.where(lab == i)
        regions.append((int(xs.min() * s), int(ys.min() * s),
                        int(min((xs.max() + 1) * s, w)), int(min((ys.max() + 1) * s, h))))
    stats["blocks_flagged"] = int(bmask.sum())
    verdict = "TAMPERED" if ratio > tamper_threshold else "AUTHENTIC"
    return VerifyResult(verdict, True, payload, conf, block_agreement, ratio, mask, regions, stats)
