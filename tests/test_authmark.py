import pytest

from authmark import derive_key, embed, verify
from authmark import attacks as A
from authmark.metrics import psnr
from authmark.synth import make_image

KEY = derive_key("test")


@pytest.fixture(scope="module")
def pair():
    im = make_image(512, 3)
    return im, embed(im, KEY, 777, timestamp=1_700_000_000)


def test_invisible(pair):
    assert psnr(*pair) > 38


def test_roundtrip(pair):
    r = verify(pair[1], KEY)
    assert r.is_authentic and r.payload.creator_id == 777 and r.payload.timestamp == 1_700_000_000


def test_non_multiple_size():
    im = make_image(512, 4).crop((0, 0, 437, 389))
    assert verify(embed(im, KEY, 5), KEY).is_authentic


def test_unwatermarked_rejected(pair):
    assert verify(pair[0], KEY).verdict == "NOT_VERIFIED"


def test_wrong_key_rejected(pair):
    assert not verify(pair[1], derive_key("other")).signature_valid


@pytest.mark.parametrize("f", [lambda x: A.jpeg(x, 75), lambda x: A.gaussian_noise(x, 4),
                               lambda x: A.brightness(x, 1.15), A.rescale_roundtrip])
def test_benign_processing_survives(pair, f):
    assert verify(f(pair[1]), KEY).is_authentic


def test_tamper_localised(pair):
    r = verify(A.paste_patch(pair[1], (0.3, 0.3, 0.6, 0.6)), KEY)
    assert r.verdict == "TAMPERED" and r.regions
    x0, y0, x1, y1 = r.regions[0]
    assert x0 < 0.6 * 512 and x1 > 0.3 * 512 and y0 < 0.6 * 512 and y1 > 0.3 * 512


def test_too_small():
    with pytest.raises(ValueError):
        embed(make_image(128), KEY, 1)
