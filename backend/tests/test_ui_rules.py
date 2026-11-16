"""Design-system rules (docs/design.md). Human-owned: the agent may not edit this file.

Templates and stylesheets listed in tests/ui_legacy.txt are still on the old layout and are
skipped. Each migration task removes its lines from that file; when it is empty, every page
follows the rules.
"""

import re
from pathlib import Path

import pytest

APP = Path(__file__).resolve().parents[1] / "app"
TEMPLATES = APP / "templates"
CSS = APP / "static" / "css"
LEGACY_FILE = Path(__file__).with_name("ui_legacy.txt")

# Files that are allowed to break a rule because they define it.
COMPONENTS = {"_ui.html"}
LAYOUTS = {"base.html", "legacy_base.html"}
TOKENS = {"tokens.css"}

COLOUR = re.compile(r"#[0-9a-fA-F]{3,8}\b|\brgba?\(|\bhsla?\(")
RAW_CONTROL = re.compile(r"<(button|input|select|textarea)\b", re.IGNORECASE)
STYLE_ATTR = re.compile(r"\sstyle\s*=", re.IGNORECASE)
H1 = re.compile(r"<h1\b", re.IGNORECASE)
LITERAL_FONT_SIZE = re.compile(r"font-size\s*:\s*[0-9.]+(px|rem|em|pt)", re.IGNORECASE)
LITERAL_FONT_FAMILY = re.compile(r"font-family\s*:(?!\s*var\()", re.IGNORECASE)


def legacy() -> set[str]:
    if not LEGACY_FILE.exists():
        return set()
    lines = LEGACY_FILE.read_text().splitlines()
    return {ln.strip() for ln in lines if ln.strip() and not ln.startswith("#")}


def strip_jinja_comments(text: str) -> str:
    """Drop Jinja comments and the theme-color meta tag (which must hold a literal colour)."""
    text = re.sub(r"\{#.*?#\}", "", text, flags=re.DOTALL)
    return re.sub(r'<meta name="theme-color"[^>]*>', "", text)


def templates() -> list[Path]:
    skip = legacy()
    return sorted(
        p for p in TEMPLATES.rglob("*.html") if p.relative_to(TEMPLATES).as_posix() not in skip
    )


def stylesheets() -> list[Path]:
    skip = legacy()
    return sorted(
        p for p in CSS.rglob("*.css") if p.name not in TOKENS and f"css/{p.name}" not in skip
    )


def is_page(path: Path) -> bool:
    rel = path.relative_to(TEMPLATES).as_posix()
    return not (
        rel in COMPONENTS
        or rel in LAYOUTS
        or path.name.startswith("_")
        or rel.startswith("partials/")
    )


@pytest.mark.parametrize("path", templates(), ids=lambda p: p.name)
def test_template_has_no_inline_style_or_colour(path: Path) -> None:
    text = strip_jinja_comments(path.read_text())
    assert not STYLE_ATTR.search(text), (
        f"{path.name}: no style= attributes; use classes from components.css/pages.css"
    )
    assert not COLOUR.search(text), f"{path.name}: no colour literals; use tokens"


@pytest.mark.parametrize(
    "path", [p for p in templates() if p.name not in COMPONENTS], ids=lambda p: p.name
)
def test_template_uses_ui_macros_for_controls(path: Path) -> None:
    text = strip_jinja_comments(path.read_text())
    match = RAW_CONTROL.search(text)
    assert not match, (
        f"{path.name}: raw <{match.group(1) if match else ''}>; use the ui.* macros from _ui.html"
    )


@pytest.mark.parametrize("path", [p for p in templates() if is_page(p)], ids=lambda p: p.name)
def test_page_extends_base_and_imports_ui(path: Path) -> None:
    text = strip_jinja_comments(path.read_text())
    assert '{% extends "base.html" %}' in text, f"{path.name}: pages extend base.html"
    if "ui." in text:
        assert '{% import "_ui.html" as ui %}' in text, f"{path.name}: import _ui.html as ui"
    assert not H1.search(text), (
        f"{path.name}: the nav bar is the page's only <h1>; set the title block instead"
    )


@pytest.mark.parametrize("path", stylesheets(), ids=lambda p: p.name)
def test_stylesheet_uses_tokens(path: Path) -> None:
    text = re.sub(r"/\*.*?\*/", "", path.read_text(), flags=re.DOTALL)
    assert not COLOUR.search(text), f"{path.name}: colours live in tokens.css only"
    assert not LITERAL_FONT_SIZE.search(text), f"{path.name}: font sizes come from --fs-* tokens"
    assert not LITERAL_FONT_FAMILY.search(text), f"{path.name}: fonts come from --font"


def test_one_jinja_environment() -> None:
    hits = [
        p
        for p in APP.rglob("*.py")
        if re.search(r"\b(Environment|Jinja2Templates)\(", p.read_text())
    ]
    assert len(hits) == 1, f"exactly one Jinja environment, found in: {[str(h) for h in hits]}"


def test_legacy_list_only_names_existing_files() -> None:
    for name in legacy():
        path = CSS / name.removeprefix("css/") if name.startswith("css/") else TEMPLATES / name
        assert path.exists(), f"ui_legacy.txt names {name}, which does not exist; remove the line"
