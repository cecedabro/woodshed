"""Static files are re-checked by the browser on every use, so a deploy reaches phones at once."""

from fastapi.testclient import TestClient


def test_static_files_must_be_revalidated(anon_client: TestClient) -> None:
    resp = anon_client.get("/static/css/tokens.css")
    assert resp.status_code == 200
    assert resp.headers["cache-control"] == "no-cache"
    assert resp.headers.get("etag")


def test_unchanged_static_file_gives_304(anon_client: TestClient) -> None:
    etag = anon_client.get("/static/css/tokens.css").headers["etag"]
    again = anon_client.get("/static/css/tokens.css", headers={"If-None-Match": etag})
    assert again.status_code == 304
    assert again.headers["cache-control"] == "no-cache"
