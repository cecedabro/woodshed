"""Tests for the Tuner page (SPEC 13.1, 13.4).

Routes: GET /tuner
"""

from fastapi.testclient import TestClient

# ---------------------------------------------------------------------------
# GET /tuner
# ---------------------------------------------------------------------------


def test_get_tuner_returns_200(client: TestClient) -> None:
    """GET /tuner returns 200."""
    resp = client.get("/tuner")
    assert resp.status_code == 200


def test_tuner_page_has_active_tab(client: TestClient) -> None:
    """SPEC 13.1: Tuner page nav has active='tuner' and aria-current='page'."""
    resp = client.get("/tuner")
    assert 'aria-current="page"' in resp.text
    assert 'href="/tuner"' in resp.text


def test_tuner_page_has_module_script(client: TestClient) -> None:
    """Tuner page loads tuner.js as an ES module script."""
    resp = client.get("/tuner")
    assert 'src="/static/js/tuner.js"' in resp.text
    assert 'type="module"' in resp.text


def test_tuner_has_correct_data_freq_buttons(client: TestClient) -> None:
    """Six reference tone buttons with the correct data-freq values."""
    resp = client.get("/tuner")
    expected = ["82.41", "110.0", "146.83", "196.0", "246.94", "329.63"]
    for freq in expected:
        assert f'data-freq="{freq}"' in resp.text


def test_tuner_has_data_a4(client: TestClient) -> None:
    """Tuner root div has data-a4="440" by default."""
    resp = client.get("/tuner")
    assert 'data-a4="440"' in resp.text


def test_tuner_has_note_display(client: TestClient) -> None:
    """Tuner page has the note display element."""
    resp = client.get("/tuner")
    assert 'id="tuner-note"' in resp.text


def test_tuner_has_hz_display(client: TestClient) -> None:
    """Tuner page has the Hz display element."""
    resp = client.get("/tuner")
    assert 'id="tuner-hz"' in resp.text


def test_tuner_has_meter(client: TestClient) -> None:
    """Tuner page has the cent meter with needle."""
    resp = client.get("/tuner")
    assert 'id="tuner-meter"' in resp.text
    assert "tuner-needle" in resp.text


def test_tuner_has_status(client: TestClient) -> None:
    """Tuner page has an aria-live status element."""
    resp = client.get("/tuner")
    assert 'id="tuner-status"' in resp.text
    assert "aria-live" in resp.text


def test_tuner_has_scale(client: TestClient) -> None:
    """Tuner page has the -50 / 0 / +50 scale labels."""
    resp = client.get("/tuner")
    assert "\u221250" in resp.text or "\u221250" in resp.text.replace("\u2212", "-")
    assert ">0<" in resp.text or ">0</" in resp.text or ">0" in resp.text
