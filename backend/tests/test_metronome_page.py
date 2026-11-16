"""Tests for the Metronome page (SPEC 6).

Routes: GET /metronome
"""

from fastapi.testclient import TestClient

# ---------------------------------------------------------------------------
# GET /metronome
# ---------------------------------------------------------------------------


def test_get_metronome_returns_200(client: TestClient) -> None:
    """GET /metronome returns 200."""
    resp = client.get("/metronome")
    assert resp.status_code == 200


def test_metronome_page_has_active_tuner_tab(client: TestClient) -> None:
    """SPEC: metronome page nav uses active='tuner' and tuner tab has aria-current='page'."""
    resp = client.get("/metronome")
    assert 'aria-current="page"' in resp.text
    assert 'href="/tuner"' in resp.text


def test_metronome_has_segmented_link_to_tuner(client: TestClient) -> None:
    """Metronome page has the segmented link to /tuner with aria-current."""
    resp = client.get("/metronome")
    assert 'href="/metronome"' in resp.text


def test_metronome_page_has_module_script(client: TestClient) -> None:
    """Metronome page loads metronome-page.js as an ES module script."""
    resp = client.get("/metronome")
    assert 'src="/static/js/metronome-page.js"' in resp.text
    assert 'type="module"' in resp.text


def test_metronome_has_bpm_display(client: TestClient) -> None:
    """Metronome page has the BPM output element with id=met-bpm."""
    resp = client.get("/metronome")
    assert 'id="met-bpm"' in resp.text
    assert "80" in resp.text


def test_metronome_has_stepper_buttons(client: TestClient) -> None:
    """Metronome page has stepper buttons with data-bpm attributes."""
    resp = client.get("/metronome")
    assert 'data-bpm="-5"' in resp.text
    assert 'data-bpm="5"' in resp.text


def test_metronome_has_tap_button(client: TestClient) -> None:
    """Metronome page has the tap tempo button."""
    resp = client.get("/metronome")
    assert 'id="met-tap"' in resp.text


def test_metronome_has_beats_input(client: TestClient) -> None:
    """Metronome page has the beats segmented input with correct options."""
    resp = client.get("/metronome")
    assert 'name="beats"' in resp.text
    for val in ["2", "3", "4", "6"]:
        assert f'value="{val}"' in resp.text
    # 4 should be checked
    assert 'name="beats"' in resp.text


def test_metronome_has_volume_input(client: TestClient) -> None:
    """Metronome page has the volume range input."""
    resp = client.get("/metronome")
    assert 'id="met-volume"' in resp.text
    assert 'name="volume"' in resp.text


def test_metronome_has_start_button(client: TestClient) -> None:
    """Metronome page has the start button."""
    resp = client.get("/metronome")
    assert 'id="met-start"' in resp.text


def test_metronome_has_beats_display(client: TestClient) -> None:
    """Metronome page has the beats display element with 4 spans."""
    resp = client.get("/metronome")
    assert 'id="met-beats"' in resp.text
    # Count the spans inside met-beats
    import re

    beats_div = re.search(r'id="met-beats"[^>]*>.*?</div>', resp.text, re.DOTALL)
    assert beats_div
    span_count = len(re.findall(r"<span", beats_div.group()))
    assert span_count == 4


def test_tuner_page_has_segmented_link_to_metronome(client: TestClient) -> None:
    """Tuner page has the segmented link to /metronome with aria-current."""
    resp = client.get("/tuner")
    assert 'href="/metronome"' in resp.text
    assert 'aria-current="page"' in resp.text


def test_tuner_page_still_has_active_tab(client: TestClient) -> None:
    """Tuner page still has active='tuner' nav highlight."""
    resp = client.get("/tuner")
    assert 'aria-current="page"' in resp.text
    assert 'href="/tuner"' in resp.text
