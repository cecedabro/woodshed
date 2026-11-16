"""Layout tests: nav, htmx and stylesheet links, local_time filter."""

from datetime import UTC, datetime
from html.parser import HTMLParser


class _NavLinkParser(HTMLParser):
    """Extract <a> tags inside the main <nav aria-label="Main">."""

    def __init__(self) -> None:
        super().__init__()
        self.nav: list[dict] = []
        self._in_nav = False
        self._in_a = False
        self._attrs: dict[str, str] = {}

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag == "nav" and ("aria-label", "Main") in attrs:
            self._in_nav = True
        if self._in_nav and tag == "a":
            self._in_a = True
            self._attrs = {k: v or "" for k, v in attrs}

    def handle_endtag(self, tag: str) -> None:
        if tag == "nav":
            self._in_nav = False
        if self._in_nav and tag == "a":
            self._in_a = False
            self.nav.append(self._attrs.copy())


def _nav_links(html: str) -> list[dict[str, str]]:
    p = _NavLinkParser()
    p.feed(html)
    return p.nav


def test_nav_has_tabs_and_settings(client) -> None:
    """SPEC 10.1: Home, Library, Routines, Tuner, Progress, plus Settings (sidebar on desktop)."""
    r = client.get("/library")
    assert r.status_code == 200
    hrefs = [a["href"] for a in _nav_links(r.text)]
    assert hrefs == ["/", "/library", "/routines", "/tuner", "/progress", "/settings"]


def test_nav_aria_current(client) -> None:
    """SPEC 10.1: only the current page has aria-current='page'."""
    r = client.get("/library")
    current = [a for a in _nav_links(r.text) if a.get("aria-current") == "page"]
    assert [a["href"] for a in current] == ["/library"]


def test_htmx_and_design_css_linked(client) -> None:
    """The base template links htmx and the three design-system stylesheets (SPEC 12.2)."""
    text = client.get("/library").text
    assert '<script src="/static/vendor/htmx.min.js"></script>' in text
    for css in ("tokens.css", "components.css", "pages.css"):
        assert f'href="/static/css/{css}"' in text


def test_local_time_winter() -> None:
    """local_time for a winter UTC time -> Europe/Amsterdam (UTC+1)."""
    from app.templating import local_time

    utc = datetime(2026, 1, 6, 18, 5, tzinfo=UTC)
    result = local_time(utc)
    assert result == "Tue 6 Jan, 19:05"


def test_local_time_summer() -> None:
    """local_time for a summer UTC time -> Europe/Amsterdam (UTC+2, DST)."""
    from app.templating import local_time

    utc = datetime(2026, 7, 15, 17, 30, tzinfo=UTC)
    result = local_time(utc)
    assert result == "Wed 15 Jul, 19:30"
