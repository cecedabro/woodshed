"""Security headers and Origin check (SPEC 10.5, 2.6)."""

from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

SECURITY_HEADERS = {
    "X-Content-Type-Options": "nosniff",
    "Referrer-Policy": "same-origin",
    "X-Frame-Options": "DENY",
    "Content-Security-Policy": (
        "default-src 'self'; "
        "style-src 'self' 'unsafe-inline'; "
        "img-src 'self' data: blob:; "
        "media-src 'self' blob:"
    ),
}


class SecurityMiddleware(BaseHTTPMiddleware):
    """Adds security headers to every response and rejects cross-origin non-safe requests."""

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        # SPEC 2.6: reject POST/PUT/DELETE/PATCH/OPTIONS with a foreign Origin
        if request.method not in ("GET", "HEAD"):
            origin = request.headers.get("origin")
            if origin is not None:
                expected = f"{request.url.scheme}://{request.url.hostname}"
                if origin != expected:
                    return JSONResponse(
                        {"detail": "Forbidden"},
                        status_code=403,
                    )

        response = await call_next(request)
        for header, value in SECURITY_HEADERS.items():
            response.headers[header] = value
        return response
