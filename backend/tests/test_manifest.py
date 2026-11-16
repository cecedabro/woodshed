"""Web app manifest and icons (SPEC 10.3)."""

import struct
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

ICONS = Path(__file__).resolve().parents[1] / "app" / "static" / "icons"


def png_size(data: bytes) -> tuple[int, int]:
    assert data[:8] == b"\x89PNG\r\n\x1a\n", "not a PNG"
    assert data[12:16] == b"IHDR"
    width, height = struct.unpack(">II", data[16:24])
    return width, height


def test_manifest_open_without_login(anon_client: TestClient) -> None:
    resp = anon_client.get("/manifest.webmanifest")
    assert resp.status_code == 200
    assert resp.headers["content-type"].startswith("application/manifest+json")
    data = resp.json()
    assert data["name"] == "Woodshed"
    assert data["display"] == "standalone"
    assert data["start_url"] == "/"
    assert data["theme_color"].startswith("#")
    assert {i["sizes"] for i in data["icons"]} == {"192x192", "512x512"}
    assert {i["purpose"] for i in data["icons"]} == {"any", "maskable"}


@pytest.mark.parametrize(
    ("name", "size"),
    [("icon-192.png", 192), ("icon-512.png", 512), ("apple-touch-icon.png", 180)],
)
def test_icon_files_have_the_right_size(anon_client: TestClient, name: str, size: int) -> None:
    resp = anon_client.get(f"/static/icons/{name}")
    assert resp.status_code == 200
    assert png_size(resp.content) == (size, size)


def test_manifest_icons_exist(anon_client: TestClient) -> None:
    for icon in anon_client.get("/manifest.webmanifest").json()["icons"]:
        assert anon_client.get(icon["src"]).status_code == 200, icon["src"]


def test_base_links_manifest_and_touch_icon(client: TestClient) -> None:
    page = client.get("/styleguide").text  # a page on base.html
    assert '<link rel="manifest" href="/manifest.webmanifest">' in page
    assert 'href="/static/icons/apple-touch-icon.png"' in page
