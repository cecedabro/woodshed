"""Pure cookie sign / verify for `ws_session` (SPEC 2.2, docs/backend.md §auth).

Cookie format: `<expiry_unix_seconds>.<hex HMAC-SHA256>`
"""

import hashlib
import hmac


def sign(expiry: int, secret: str) -> str:
    """Return a signed cookie string for the given expiry timestamp."""
    data = f"{expiry}."
    h = hmac.new(secret.encode(), data.encode(), hashlib.sha256)
    return f"{data}{h.hexdigest()}"


def verify(cookie: str, secret: str, now: int) -> bool:
    """Return True when *cookie* is a valid, unexpired cookie."""
    parts = cookie.split(".")
    if len(parts) != 2:
        return False

    expiry_str, sig = parts

    # non-numeric expiry → reject
    try:
        expiry = int(expiry_str)
    except ValueError:
        return False

    if now >= expiry:
        return False

    expected = sign(expiry, secret)
    return hmac.compare_digest(expected, cookie)
