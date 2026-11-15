"""Login flow and cookie helpers (SPEC 2.1–2.5).

Cookie helpers ``sign`` / ``verify`` are pure functions exported for tests.
Routes: GET /login, POST /login, POST /logout
"""

import hashlib
import hmac
import time
from datetime import datetime, timedelta
from typing import Any

from fastapi import Depends, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from starlette.responses import Response

from app.config import Settings
from app.templating import env

# ---------------------------------------------------------------------------
# Pure cookie sign / verify (SPEC 2.2)
# ---------------------------------------------------------------------------


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

    try:
        expiry = int(expiry_str)
    except ValueError:
        return False

    if now >= expiry:
        return False

    expected = sign(expiry, secret)
    return hmac.compare_digest(expected, cookie)


# ---------------------------------------------------------------------------
# Dependency
# ---------------------------------------------------------------------------


def _get_settings(request: Request) -> Settings:
    """Dependency to retrieve Settings from the app state."""
    return request.app.state.settings  # type: ignore[no-any-return]


# ---------------------------------------------------------------------------
# Login check dependency
# ---------------------------------------------------------------------------


def require_login(request: Request) -> None:
    """Raise HTTPException(401) if the user has no valid session cookie."""
    settings = _get_settings(request)
    if _parse_cookie(request, settings.SESSION_SECRET) is None:
        from fastapi import HTTPException

        raise HTTPException(status_code=401, detail="Login required")


# ---------------------------------------------------------------------------
# Cookie helpers
# ---------------------------------------------------------------------------


def _make_cookie_value(expiry: int, secret: str) -> str:
    return sign(expiry, secret)


def _parse_cookie(request: Request, secret: str) -> int | None:
    """Return expiry unix seconds if *ws_session* is valid, else None."""
    cookie = request.cookies.get("ws_session")
    if cookie is None:
        return None
    now = int(time.time())
    expiry = int(cookie.split(".")[0]) if "." in cookie else 0
    return expiry if verify(cookie, secret, now) else None


def _set_session_cookie(response: Response, expiry: int, secret: str, production: bool) -> None:
    response.set_cookie(
        key="ws_session",
        value=_make_cookie_value(expiry, secret),
        max_age=90 * 24 * 3600,
        httponly=True,
        samesite="lax",
        path="/",
        secure=production,
    )


def _clear_session_cookie(response: Response, production: bool) -> None:
    response.delete_cookie(key="ws_session", path="/", secure=production, samesite="lax")


# ---------------------------------------------------------------------------
# Rate-limit helpers
# ---------------------------------------------------------------------------

RATE_LIMIT_MAX = 10
_RATE_WINDOW = timedelta(minutes=15)


def _prune_failures(state: Any, now: datetime) -> None:
    cutoff = now - _RATE_WINDOW
    failures = getattr(state, "_failed_logins", None)
    if failures is None:
        state._failed_logins = []
        return
    state._failed_logins = [t for t in failures if t > cutoff]


def _is_rate_limited(state: Any, now: datetime) -> bool:
    _prune_failures(state, now)
    return len(state._failed_logins) >= RATE_LIMIT_MAX


def _record_failure(state: Any, now: datetime) -> None:
    _prune_failures(state, now)
    state._failed_logins.append(now)


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------


def _open_template(template_name: str, extra: dict[str, Any] | None = None) -> HTMLResponse:
    data = {"active": None, "error": None, **(extra or {})}
    template = env.get_template(template_name)
    return HTMLResponse(template.render(data))


def get_login(request: Request, settings: Settings = Depends(_get_settings)) -> HTMLResponse:
    return _open_template("login.html")


def post_login(
    request: Request,
    password: str = Form(...),
    settings: Settings = Depends(_get_settings),
) -> Response:
    from app import clock

    now = clock.now()

    # Rate limit check
    if _is_rate_limited(request.app.state, now):
        template = env.get_template("login.html")
        return HTMLResponse(
            template.render({"active": None, "error": "Too many attempts. Wait 15 minutes."}),
            status_code=429,
        )

    production = settings.APP_ENV == "production"
    correct = password == settings.APP_PASSWORD

    if correct:
        expiry = int(now.timestamp()) + 90 * 24 * 3600
        response = RedirectResponse(url="/", status_code=303)
        _set_session_cookie(response, expiry, settings.SESSION_SECRET, production)
        # Clear failed attempts on successful login
        request.app.state._failed_logins = []
        return response
    else:
        # Record failure
        _record_failure(request.app.state, now)
        return _open_template("login.html", {"error": "Wrong password"})


def post_logout(request: Request, settings: Settings = Depends(_get_settings)) -> Response:
    production = settings.APP_ENV == "production"
    response = RedirectResponse(url="/login", status_code=303)
    _clear_session_cookie(response, production)
    return response
