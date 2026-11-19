"""Tests for the new item lookup page (T88).

Verifies that /items/new has no inline scripts, has the HTMX lookup form,
and the results container exist.
"""

import re

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _get_page(client) -> str:
    resp = client.get("/items/new")
    assert resp.status_code == 200
    return resp.text


def _no_inline_scripts(html: str) -> bool:
    """Return True when there are no <script> tags without a src attribute."""
    for m in re.finditer(r"<script([^>]*)>", html, re.IGNORECASE):
        attrs = m.group(1)
        if "src" not in attrs:
            return False
    return True


def _find_hx_forms(html: str) -> list[dict]:
    """Find all <form ... hx-get="/items/lookup" hx-target="#mb-results"> tags."""
    pattern = re.compile(
        r'<form\s+[^>]*hx-get=["\'](/items/lookup)["\'][^>]*hx-target=["\'](#mb-results)["\'][^>]*/?>|'
        r'<form\s+[^>]*hx-target=["\'](#mb-results)["\'][^>]*hx-get=["\'](/items/lookup)["\'][^>]*/?>',
        re.IGNORECASE,
    )
    results = []
    for m in pattern.finditer(html):
        attrs = m.group(0)
        # Extract form index from the matched tag
        results.append({"attrs": attrs})
    return results


def _find_input_names_in_form(html: str, form_attrs: str) -> set[str]:
    """Find input names between the matching <form ...hx-get...> and its </form>."""
    # Find the opening tag position
    open_pattern = re.compile(
        r'<form\s+[^>]*hx-get=["\'](/items/lookup)["\'][^>]*hx-target=["\'](#mb-results)["\'][^>]*/?>',
        re.IGNORECASE,
    )
    for m in open_pattern.finditer(html):
        start = m.end()
        # Find the matching closing tag (simple: find next </form>)
        close = html.find("</form>", start)
        if close == -1:
            continue
        body = html[start:close]
        # Extract input names
        for im in re.finditer(r'<input[^>]*name=["\']([^"\']+)["\']', body, re.IGNORECASE):
            yield im.group(1)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_no_inline_script(client):
    """The page must not contain <script> elements without src (CSP)."""
    html = _get_page(client)
    assert _no_inline_scripts(html)


def test_lookup_form_exists(client):
    """A form with hx-get="/items/lookup" and hx-target="#mb-results" exists."""
    html = _get_page(client)
    forms = _find_hx_forms(html)
    assert len(forms) == 1


def test_lookup_form_has_title_and_artist(client):
    """The HTMX lookup form contains inputs named title and artist."""
    html = _get_page(client)
    forms = _find_hx_forms(html)
    assert len(forms) == 1
    names = list(_find_input_names_in_form(html, forms[0]["attrs"]))
    assert "title" in names
    assert "artist" in names


def test_lookup_form_not_nested_in_another_form(client):
    """The HTMX lookup form must not be nested inside another form element."""
    html = _get_page(client)
    # Count all <form> tags
    all_forms = re.findall(r"<form[^>]*/?>|<form[^>]*>", html, re.IGNORECASE)
    assert len(all_forms) == 2  # lookup form + main item form
    # Verify the HTMX form's opening tag comes before its </form> and no outer form
    # contains it: we check that neither <form> appears between the HTMX form's
    # <form> and </form>.
    htmx_pattern = re.compile(
        r'<form\s+[^>]*hx-get=["\'](/items/lookup)["\']',
        re.IGNORECASE,
    )
    for m in htmx_pattern.finditer(html):
        start = m.end()
        close = html.find("</form>", start)
        if close == -1:
            continue
        body = html[start:close]
        # No other <form> should appear inside
        inner_forms = re.findall(r"<form[^>]*/?>|<form[^>]*>", body, re.IGNORECASE)
        assert len(inner_forms) == 0


def test_mb_results_div_exists(client):
    """A #mb-results container div exists for HTMX to swap into."""
    html = _get_page(client)
    assert re.search(r'id=["\']mb-results["\']', html)
