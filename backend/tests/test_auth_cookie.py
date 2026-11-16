"""Pure cookie sign / verify (SPEC 2.2, docs/backend.md §auth).

Tests for `sign()` and `verify()` in `app/auth.py`.
"""

from app.auth import sign, verify

SECS = 1000  # shorthand for one second in seconds
NOW = 1_700_000_000  # a fixed epoch-second used as "now" for every test
EXPIRY = NOW + 90 * SECS * 24 * 60 * 60  # 90 days from NOW
SECRET = "test-session-secret-32-chars-long-enough!"


def test_fresh_cookie_verifies() -> None:
    """A freshly-signed cookie verifies as True."""
    cookie = sign(EXPIRY, SECRET)
    assert verify(cookie, SECRET, NOW) is True


def test_wrong_secret_fails() -> None:
    """A cookie signed with a different secret does not verify."""
    cookie = sign(EXPIRY, "completely-different-secret-value!!")
    assert verify(cookie, SECRET, NOW) is False


def test_edited_expiry_fails() -> None:
    """Tampering the expiry number (but keeping the dot) breaks verification."""
    cookie = sign(EXPIRY, SECRET)
    # Replace the expiry number part — swap 1234 for 9999
    old_expiry_str = str(EXPIRY)
    new_expiry_str = "9999999999"
    tampered = cookie.replace(old_expiry_str, new_expiry_str, 1)
    assert verify(tampered, SECRET, NOW) is False


def test_edited_signature_fails() -> None:
    """Flipping a single hex character in the signature breaks verification."""
    cookie = sign(EXPIRY, SECRET)
    # Find the signature part (after the dot)
    dot_pos = cookie.index(".")
    sig = cookie[dot_pos + 1 :]
    # Flip first character
    flipped = "1" if sig[0] != "1" else "0"
    tampered = cookie[: dot_pos + 1] + flipped + sig[1:]
    assert verify(tampered, SECRET, NOW) is False


def test_missing_dot_fails() -> None:
    """A cookie with no dot at all is rejected."""
    # Build a string with no dot — just expiry + signature concatenated
    raw_cookie = sign(EXPIRY, SECRET)
    no_dot = raw_cookie.replace(".", "")
    assert verify(no_dot, SECRET, NOW) is False


def test_non_numeric_expiry_fails() -> None:
    """Expiry that isn't an integer is rejected."""
    # Replace the numeric expiry with letters
    cookie = sign(EXPIRY, SECRET)
    old_expiry_str = str(EXPIRY)
    tampered = cookie.replace(old_expiry_str, "notanumber", 1)
    assert verify(tampered, SECRET, NOW) is False


def test_expired_cookie_fails() -> None:
    """A cookie whose expiry is in the past does not verify."""
    cookie = sign(EXPIRY, SECRET)
    # Use a "now" well past expiry
    assert verify(cookie, SECRET, EXPIRY + 1) is False
