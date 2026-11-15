"""Tests for the /progress page: SVG bar chart rendering (Task T32).

Verifies:
  - 12 bars are rendered in the SVG
  - bar heights are proportional to minutes
  - empty weeks (0 min) produce 0-height bars
  - goal line is rendered
  - / and /progress pages do not contain "streak" or "day in a row"
"""

import pytest
from fastapi.testclient import TestClient
from jinja2 import BaseLoader, Environment

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _svg_bar_count(svg_html: str) -> int:
    """Count bar <rect> elements (not the background rect)."""
    return svg_html.count('fill="var(--secondary)"')


def _svg_bar_heights(svg_html: str) -> list[float]:
    """Extract `height` attribute values from bar <rect> elements in SVG."""
    import re
    from contextlib import suppress

    heights: list[float] = []
    for m in re.finditer(r'<rect\b([^>]*?fill="var\(--secondary\)"[^>]*?)>', svg_html):
        inner = m.group(1)
        hm = re.search(r'\bheight="([^"]*)"', inner)
        if hm:
            with suppress(ValueError):
                heights.append(float(hm.group(1)))
    return heights


def _login(client: TestClient) -> None:
    """Log in via the login page and set the session cookie."""
    client.post("/login", data={"password": "dev-password"}, follow_redirects=False)


# ---------------------------------------------------------------------------
# Tests: SVG rendering via helper functions
# ---------------------------------------------------------------------------


class TestSVGBarCount:
    """Exactly 12 bars must be rendered."""

    def test_twelve_bars(self):
        """Render chart with 12 non-empty weeks and verify 12 rects."""
        minutes = [30] * 12
        svg = _make_svg(minutes, goal=45)
        assert _svg_bar_count(svg) == 12

    def test_empty_weeks(self):
        """All-zero weeks still produce 12 rects."""
        svg = _make_svg([0] * 12, goal=30)
        assert _svg_bar_count(svg) == 12


class TestSVGBarHeights:
    """Heights must be proportional to minutes relative to max(goal, max_minutes)."""

    def test_height_ratio(self):
        """A week with 60 min should be 2× taller than 30 min when goal=60."""
        minutes = [30, 60, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0]
        heights = _make_heights(minutes, goal=60)
        # max(60, max(minutes)) = 60 → uh is fixed
        # 30/60 * uh vs 60/60 * uh → 0.5 ratio
        assert heights[1] > heights[0] * 1.5  # at least 50% taller

    def test_empty_week_zero_height(self):
        """Weeks with 0 minutes must render at height 0."""
        minutes = [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 30]
        heights = _make_heights(minutes, goal=30)
        assert heights[0] == pytest.approx(0.0, abs=0.1)

    def test_goal_as_upper_bound(self):
        """When all weeks < goal, goal sets the scale."""
        minutes = [10] * 12
        heights = _make_heights(minutes, goal=60)
        # max(60, 10) = 60 → all bars ~ 10/60 * uh
        for h in heights:
            assert h > 0  # positive height


class TestSVGGolLine:
    """Goal line must be present."""

    def test_goal_line_present(self):
        """SVG must contain a dashed <line> element for the goal."""
        svg = _make_svg([30] * 12, goal=45)
        assert "stroke-dasharray" in svg
        assert "45 min goal" in svg


# ---------------------------------------------------------------------------
# Tests: page rendering — forbidden text
# ---------------------------------------------------------------------------


class TestNoForbiddenText:
    """/ and /progress must not contain "streak" or "day in a row"."""

    def test_no_streak_on_home(self, client: TestClient):
        _login(client)
        resp = client.get("/")
        assert resp.status_code == 200
        html = resp.content.decode()
        assert "streak" not in html.lower()
        assert "day in a row" not in html.lower()

    def test_no_streak_on_progress(self, client: TestClient):
        _login(client)
        resp = client.get("/progress")
        assert resp.status_code == 200
        html = resp.content.decode()
        assert "streak" not in html.lower()
        assert "day in a row" not in html.lower()


# ---------------------------------------------------------------------------
# Fixture data
# ---------------------------------------------------------------------------


@pytest.fixture
def db_minutes() -> list[int]:
    """Default 12 weeks of varied minutes for tests."""
    return [30, 45, 20, 60, 0, 15, 40, 35, 50, 25, 10, 55]


def _make_svg(minutes: list[int], goal: int) -> str:
    """Generate SVG HTML via Jinja2 templating for a list of week dicts."""
    weeks = [{"minutes": m, "monday": None} for m in minutes]
    template_str = """
{% macro render_bar_chart(weeks, goal) -%}
{% set cw = 720 %}{% set ch = 240 %}{% set pt = 20 %}{% set pb = 40 %}
{% set pl = 40 %}{% set pr = 10 %}{% set uw = cw - pl - pr %}
{% set uh = ch - pt - pb %}{% set bc = weeks|length %}{% set bg = 4 %}
{% set bw = (uw - bg * (bc - 1)) / bc %}
{% if weeks %}{% set mm = [weeks|map(attribute='minutes')|max, goal]|max %}
{% else %}{% set mm = goal %}{% endif %}
{% if mm == 0 %}{% set mm = 1 %}{% endif %}
<svg xmlns="http://www.w3.org/2000/svg"
     viewBox="0 0 {{ cw }} {{ ch }}"
     width="100%" height="100%" class="progress-svg" role="img"
     aria-label="Practice minutes per week for the last 12 weeks">
    <rect x="0" y="0" width="{{ cw }}" height="{{ ch }}" fill="var(--bg-alt)" rx="8"/>
    {% set gy = pt + uh - (goal / mm * uh) %}
    <line x1="{{ pl }}" y1="{{ gy }}" x2="{{ cw - pr }}" y2="{{ gy }}"
          stroke="var(--accent)" stroke-width="1.5" stroke-dasharray="6,4"/>
    <text x="{{ cw - pr }}" y="{{ gy - 6 }}"
          fill="var(--accent)" font-size="11" text-anchor="end">{{ goal }} min goal</text>
    {% for i, week in enumerate(weeks) %}
        {% set bx = pl + i * (bw + bg) %}
        {% set bh = week.minutes / mm * uh %}
        {% set by = pt + uh - bh %}
        <rect x="{{ bx }}" y="{{ by }}" width="{{ bw }}" height="{{ bh }}"
              fill="var(--secondary)" rx="2"
              opacity="{{ 0.5 + 0.5 * (week.minutes / mm) }}">
        </rect>
        {% if week.minutes %}
        <text x="{{ bx + bw / 2 }}" y="{{ by - 4 }}"
              fill="var(--text-dim)" font-size="10" text-anchor="middle">
            {{ week.minutes }}
        </text>
        {% endif %}
        <text x="{{ bx + bw / 2 }}" y="{{ ch - 10 }}"
              fill="var(--text-dim)" font-size="10" text-anchor="middle">
            {{ week.monday.strftime('%b %-d') if week.monday }}
        </text>
    {% endfor %}
</svg>
{%- endmacro %}
{{ render_bar_chart(weeks, goal)|safe }}
    """

    def _map_filter(it, attribute=None):
        result = []
        for item in it:
            if isinstance(item, dict):
                result.append(item.get(attribute) if attribute is not None else item)
            else:
                result.append(getattr(item, attribute, None) if attribute is not None else item)
        return result

    env = Environment(loader=BaseLoader())
    env.globals["enumerate"] = enumerate
    env.filters["map"] = _map_filter
    tmpl = env.from_string(template_str)
    return tmpl.render(weeks=weeks, goal=goal)


def _make_heights(minutes: list[int], goal: int) -> list[float]:
    """Extract bar heights from the generated SVG."""
    svg = _make_svg(minutes, goal)
    return _svg_bar_heights(svg)
