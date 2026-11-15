"""Layout tests: nav, htmx link, style.css link, local_time filter (Task T03)."""

from datetime import UTC, datetime
from html.parser import HTMLParser


class _NavLinkParser(HTMLParser):
    """Extract <a> tags inside <nav>."""

    def __init__(self) -> None:
        super().__init__()
        self.nav: list[dict] = []
        self._in_nav = False
        self._in_a = False
        self._attrs: dict[str, str] = {}

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag == "nav":
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


def test_home_has_all_five_nav_links(client) -> None:
    """SPEC 10.1: every page has the five nav links."""
    client.post("/login", data={"password": "dev-password"}, follow_redirects=False)
    r = client.get("/")
    assert r.status_code == 200

    links = _nav_links(r.text)
    assert len(links) == 5

    hrefs = {a["href"] for a in links}
    assert hrefs == {"/", "/library", "/routines", "/progress", "/settings"}


def test_home_has_aria_current(client) -> None:
    """SPEC 10.1: only the current page has aria-current='page'."""
    client.post("/login", data={"password": "dev-password"}, follow_redirects=False)
    r = client.get("/")
    assert r.status_code == 200

    links = _nav_links(r.text)
    current = [a for a in links if a.get("aria-current") == "page"]
    assert len(current) == 1
    assert current[0]["href"] == "/"


def test_htmx_and_stylecss_linked(client) -> None:
    """The base template links htmx.min.js and style.css."""
    client.post("/login", data={"password": "dev-password"}, follow_redirects=False)
    r = client.get("/")
    assert r.status_code == 200
    text = r.text

    assert '<script src="/static/vendor/htmx.min.js"></script>' in text
    assert 'href="/static/style.css"' in text


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
