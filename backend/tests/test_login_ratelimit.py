"""Rate limiting on POST /login (SPEC 2.5).

After 10 failed logins within 15 minutes, POST /login returns 429 even
with the correct password.  Once the 15-minute window passes the correct
password succeeds (303 redirect).
"""

from datetime import timedelta

from fastapi.testclient import TestClient


def test_11th_attempt_returns_429(client: TestClient) -> None:
    """The 11th failed login within 15 minutes is rejected with 429."""
    wrong = "wrong-password"
    for i in range(10):
        resp = client.post("/login", data={"password": wrong}, follow_redirects=False)
        assert resp.status_code == 401, f"Attempt {i + 1} should return 401, got {resp.status_code}"

    # 11th attempt: should be 429
    resp = client.post("/login", data={"password": wrong}, follow_redirects=False)
    assert resp.status_code == 429, f"11th attempt should be 429, got {resp.status_code}"

    # Even the correct password should be rejected while rate-limited
    resp = client.post("/login", data={"password": "dev-password"}, follow_redirects=False)
    assert resp.status_code == 429, "Correct password while rate-limited should still be 429"


def test_right_password_works_after_15_minutes(client: TestClient) -> None:
    """After 15 minutes the rate limit window passes and the right password works."""
    from app import clock

    # Exhaust 10 failed attempts at current time
    for _ in range(10):
        client.post("/login", data={"password": "wrong"}, follow_redirects=False)

    # Fast-forward clock by 15 minutes so the window expires
    original_now = clock.now
    future = original_now() + timedelta(minutes=15)
    clock.now = lambda: future

    try:
        # 11th attempt with the right password should succeed
        resp = client.post("/login", data={"password": "dev-password"}, follow_redirects=False)
        assert resp.status_code == 303, f"Expected 303 after window, got {resp.status_code}"
        assert resp.headers.get("location") == "/"
    finally:
        clock.now = original_now
