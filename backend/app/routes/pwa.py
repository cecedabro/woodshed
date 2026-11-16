"""Web app manifest (SPEC 10.3, docs/frontend.md §pwa).

Route: GET /manifest.webmanifest (open without login, so the browser can fetch it).
Icons are drawn by scripts/make_icons.py; their content sits inside the maskable safe zone.
"""

from fastapi import APIRouter
from fastapi.responses import JSONResponse

router = APIRouter()

THEME_COLOUR = "#241e18"  # --c-bar, same as the theme-color meta tag in base.html
BACKGROUND_COLOUR = "#1b1714"  # --c-bg

MANIFEST = {
    "name": "Woodshed",
    "short_name": "Woodshed",
    "description": "Guitar practice organiser",
    "start_url": "/",
    "scope": "/",
    "display": "standalone",
    "theme_color": THEME_COLOUR,
    "background_color": BACKGROUND_COLOUR,
    "icons": [
        {
            "src": f"/static/icons/icon-{size}.png",
            "sizes": f"{size}x{size}",
            "type": "image/png",
            "purpose": purpose,
        }
        for size in (192, 512)
        for purpose in ("any", "maskable")
    ],
}


@router.get("/manifest.webmanifest")
def get_manifest() -> JSONResponse:
    return JSONResponse(MANIFEST, media_type="application/manifest+json")
