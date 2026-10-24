import hashlib


def derive_key(passphrase: str) -> bytes:
    """Derive a 32-byte secret key from a passphrase."""
    return hashlib.pbkdf2_hmac("sha256", passphrase.encode(), b"authmark-v1", 100_000)
