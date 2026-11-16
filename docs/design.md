# Design system

The look is decided; you **compose** pages, you don't design them. Classic iOS (grouped lists,
nav bar, tab bar, segmented controls, switches, a little gloss) in warm valve-amp colours.
On screens ≥ 900 px (Mac, iPad landscape) the tab bar becomes a sidebar and content is
centred at 760 px. `/styleguide` shows every component (`templates/styleguide.html` is also a
composition example).

## Files
| File | What | Who |
|---|---|---|
| `static/css/tokens.css` | every colour, font, size, radius, shadow; themes `flat`, `daylight` | human |
| `static/css/components.css` | all components and layout helpers, tokens only | human |
| `templates/_ui.html` | one Jinja macro per component | human |
| `templates/base.html` | app shell: sidebar/tab bar, nav bar with the page `<h1>`, content | human (T39 adds head tags) |
| `templates/styleguide.html` | every component | human |
| `static/css/pages.css` | page-specific layout, tokens only, keep it short | **agent** |
| `templates/partials/*.html` | HTMX fragments | **agent** |
| `backend/tests/test_ui_rules.py` | enforces the rules below | human |
| `backend/tests/ui_legacy.txt` | pages not migrated yet; a migration task removes its lines, never adds | agent (remove only) |

If a page needs something no component offers, use the layout helpers and `pages.css`; if
that is not enough, do the simplest thing and write the gap in PROGRESS.md. Never edit the
human-owned files.

## Rules (checked by `backend/tests/test_ui_rules.py`)
- Pages `{% extends "base.html" %}` and `{% import "_ui.html" as ui %}`.
- No `<h1>` in pages: the nav bar title is the `<h1>`; set `{% block title %}`.
- No `style=` attributes and no colour literals in templates; no raw `<button>`, `<input>`,
  `<select>`, `<textarea>` outside `_ui.html` (use the macros; `<form>` and `<a>` are fine).
- CSS outside `tokens.css`: no colour literals, no literal `font-size`, no `font-family`
  other than `var(--font)`.
- One Jinja environment in the app.
- JS never sets colours or inline styles, except the `--cents` property on `.tuner-meter`.
  It toggles classes (`is-on`, `is-done`, `is-current`, `is-in-tune`, `is-idle`), the
  `hidden` attribute and `aria-pressed`, and sets text.

## base.html
Blocks: `title` (also the nav bar `<h1>`), `nav_title` (only if the `<h1>` must differ),
`nav_left` (back link), `nav_right` (one or two actions), `content`, `content_class` (append
` content-wide` for wide pages), `head`, `scripts` (module script tags).
Context: `active` (home, library, routines, tuner, progress, settings), `theme` (provided for
every template by the app, SPEC 12.3), `bare` (True hides the tab bar/sidebar: login;
`{% set bare = True %}` in the page works).

## Macros (`ui.*`)
| Macro | Use |
|---|---|
| `icon(name, label=None)` | inline SVG: home library routines tuner progress settings play pause skip plus minus search back record music file trash edit check mic |
| `nav_link(label, href, icon_name=None, back=False)` | nav bar action; `back=True` renders "‹ label" |
| `call section(header=None, footer=None, id=None)` | section with uppercase header and a footnote |
| `call group(pad=False, attrs={})` | rounded group; rows or fields inside; `pad=True` for free content |
| `row(title, sub, href, value, thumb, tone, chevron_, attrs)` | list row; with `href` a link with chevron; `call row(...)` puts controls at the right; `tone`: accent, danger |
| `row_button(title, tone, type, attrs)` | a row that is a submit button (log out, delete) |
| `button(label, kind, type, size, block, icon_name, icon_only, attrs)` | kind: secondary (default), primary, danger, outline-danger, ghost; size: small, big |
| `link_button(label, href, kind, size, block, icon_name, attrs)` | same look as an `<a>` |
| `start(title, sub, href, attrs)` | the big amber start button (Home) |
| `field(name, label, value, type, error, hint, required, placeholder, attrs)` | labelled input in a group |
| `textarea(...)`, `select(name, label, options, selected, ...)` | options: list of (value, label) |
| `search(name, label, value, placeholder, attrs)` | search box (label visually hidden) |
| `segmented(name, label, options, selected, attrs)` | radio segmented control |
| `segmented_links(label, links)` | filter tabs; links: (href, label, current) |
| `switch_row(name, label, checked, attrs)` | row with an iOS switch (`role="switch"` checkbox) |
| `range_row(name, label, value, min, max, step, attrs)` | row with a slider |
| `stepper(label, value, id, steps)` | − value +; the buttons carry `data-step` and `data-for` |
| `alert(text, kind)` | kind ok, error, or none |
| `badge(text, accent)`, `stat(value, label)`, `empty(title, text, href, action, icon_name)` | |
| `progress(value, max, unit, aside, label)` | big number plus a native `<progress class="bar">` |

`attrs` carries anything extra, e.g. `{"hx-post": url, "hx-target": "#blocks", "id": "x",
"data-freq": "82.41", "form": "f"}`. An `attrs` `id` replaces the default `f-<name>` id.

CSS helpers: `.stack` (12 px gaps), `.stack-lg` (24 px), `.cluster` (wrapping row),
`.spread` (space-between row), `.split` (2 columns ≥ 900 px), `.actions`, `.actions-end`,
`.actions-split` (1 : 1.6 : 1 buttons), `.muted`, `.small`, `.notes` (keeps line breaks),
`.mobile-only`, `.desktop-only`, `.visually-hidden`. Runner: `.blocks`, `.runner-head`,
`.runner-title`, `.runner-sub`, `.countdown`, `.countdown-time`, `.countdown-note`, `.beats`.
Tuner: `.tuner`, `.tuner-note`, `.tuner-hz`, `.tuner-meter`, `.tuner-needle`, `.tuner-scale`,
`.tuner-status`. Charts: SVG with classes `.chart`, `.chart-bar`, `.chart-bar-dim`,
`.chart-goal`, `.chart-line`, `.chart-dot`, `.chart-axis`, `.chart-label` (no fill or stroke
colours in the SVG). Media: `.cover`, `.audio`, `.tab-viewer`.

## Page recipes
Keep every `id` and `data-*` that JS and tests already use. Copy, then fill in the data.

**Home `/`** (`active="home"`)
```jinja
{% block title %}Woodshed{% endblock %}
{% block nav_right %}<span class="mobile-only">{{ ui.nav_link("Settings", "/settings", icon_name="settings") }}</span>{% endblock %}
{% block content %}
{% call ui.section("This week", footer="Mon–Sun. No streaks, just minutes.") %}
  {% call ui.group(pad=True) %}{{ ui.progress(week_minutes, goal, aside=aside_text) }}{% endcall %}
{% endcall %}
{% call ui.section("Start practising") %}
  <div class="stack">
    {{ ui.start(first.name, first.n_blocks ~ " blocks · " ~ first.minutes ~ " min", "/run/" ~ first.id ~ "?autostart=1") }}
    {% call ui.group() %}
      {% for r in others %}{{ ui.row(r.name, sub=r.n_blocks ~ " blocks · " ~ r.minutes ~ " min", href="/run/" ~ r.id ~ "?autostart=1") }}{% endfor %}
      {{ ui.row("Practise one song…", href="/library", tone="accent") }}
    {% endcall %}
  </div>
{% endcall %}
{% endblock %}
```
`aside_text`: "45 to go", or "Goal reached" when done. No routines:
`ui.empty("No routines yet", "A routine is a list of blocks: what to play and for how long.", "/routines/new", "New routine", icon_name="routines")`.

**Library `/library`** — nav_right `ui.nav_link("Add", "/items/new", icon_name="plus")`.
A `<form method="get" class="stack">` with `ui.search("q", "Search the library", q)` and
`ui.segmented_links("Kind", [("/library", "All", not kind), ("/library?kind=song", "Songs", kind == "song"), ("/library?kind=exercise", "Exercises", kind == "exercise")])`.
Then per non-empty status a `ui.section(label)` with a `ui.group()` of
`ui.row(item.title, sub=item.artist or "Exercise", value=(item.current_bpm ~ " bpm") if item.current_bpm else None, href="/items/" ~ item.id, thumb=("/media/cover/" ~ item.id) if item.has_cover else None)`.
Empty: `ui.empty("Your library is empty", "Add the songs and exercises you're working on.", "/items/new", "Add a song")`.

**Item `/items/{id}`** — title = item title; nav_left `ui.nav_link("Library", "/library", back=True)`;
nav_right `ui.nav_link("Edit", "/items/" ~ id ~ "/edit")`. Content in `.stack-lg`:
1. `.spread`: the cover `<img class="cover" src="/media/cover/{id}" alt="">` when `has_cover`, and
   a `.stack` with the artist and `.cluster` of `ui.badge(kind)` + `ui.badge(status, accent=True)`.
   Then `ui.link_button("Practise this", "/run/item/" ~ id ~ "?minutes=10", kind="primary", size="big", block=True, icon_name="play")`.
2. `.split` with section "Details" (group of rows: Current BPM, Original link as a row with
   `href` and `attrs={"target": "_blank", "rel": "noopener"}`, Added) and section "Notes"
   (`ui.group(pad=True)` with `<p class="notes">`).
3. `.split` with section "Files" (a row per attachment: tab → `/items/{id}/tab/{att}`, PDF →
   `/media/attachment/{att}`; audio as `<audio class="audio" controls preload="none">` in a
   padded group; then the upload `<form>`: group with `ui.field("file", "File", type="file")`
   and `ui.field("label", "Label (optional)")`, `.actions` with
   `ui.button("Upload", kind="primary", type="submit")`) and section "Tempo" (history text and
   SVG with chart classes).
4. Section "Takes" (later tasks). Last: a group with `ui.row("Delete this item…", href="/items/" ~ id ~ "/delete", tone="danger")`.

**Item form (`/items/new`, `/items/{id}/edit`)** — nav_left back. `<form method="post" class="form stack-lg">`:
section "Song": group with `ui.select("kind", …)`, `ui.field("title", "Title", required=True)`,
`ui.field("artist", "Artist")`, `ui.field("year", "Year", type="number")`;
section "Practice": group with `ui.select("status", …)`, `ui.field("current_bpm", "Current BPM", type="number", hint="20–400")`,
`ui.field("original_url", "Link to the original", type="url")`;
section "Notes": group with `ui.textarea("notes", "Notes")`;
hidden values: `<div hidden>{{ ui.field("mbid", "MusicBrainz id", mbid, type="hidden") }}{{ ui.field("release_group_id", "Release group", rgid, type="hidden") }}</div>`;
`.actions.actions-end` with `ui.link_button("Cancel", back_url, kind="ghost")` and
`ui.button("Save", kind="primary", type="submit")`. Errors: `error=` on the field, status 422.
On `/items/new` the "Find the song" section comes first.

**Find the song (top of `/items/new`)**
```jinja
{% call ui.section("Find the song", footer="Song details from MusicBrainz.") %}
<form method="get" action="/items/lookup" hx-get="/items/lookup" hx-target="#mb-results"
      hx-trigger="submit, keyup changed delay:500ms from:#f-mb-title, keyup changed delay:500ms from:#f-mb-artist">
  {% call ui.group() %}{{ ui.field("title", "Title", attrs={"id": "f-mb-title"}) }}{{ ui.field("artist", "Artist (optional)", attrs={"id": "f-mb-artist"}) }}{% endcall %}
  <div class="actions actions-end">{{ ui.button("Search", type="submit", icon_name="search") }}</div>
</form>
<div id="mb-results" aria-live="polite"></div>
{% endcall %}
```
`partials/mb_results.html`: a `ui.group()` of
`ui.row(c.title, sub=c.artist ~ (" · " ~ c.year if c.year else ""), value=c.length, href=c.prefill_url)`
and a last `ui.row("Not listed? Fill it in yourself", href="#f-title", tone="accent")`.
Failure: `ui.alert("MusicBrainz didn't answer. Fill in the song yourself.", kind="error")`;
no results: `ui.alert("Nothing found.")`.

**Routines `/routines`** — nav_right `ui.nav_link("New routine", "/routines/new", icon_name="plus")`.
A group with `ui.row(r.name, sub=n ~ " blocks · " ~ minutes ~ " min", href="/routines/" ~ r.id ~ "/edit")`;
empty → `ui.empty(...)` as on Home. **New routine**: form, group with `ui.field("name", "Name", required=True)`,
actions Cancel / `ui.button("Create", kind="primary", type="submit")`.
**Delete confirmations** (item, routine): `ui.group(pad=True)` with the question as `<p>`, then
`.actions.actions-end` with Cancel (ghost link) and `ui.button("Delete", kind="danger", type="submit")`.

**Routine editor `/routines/{id}/edit`** — title = routine name; nav_left back "Routines";
nav_right `ui.nav_link("Run", "/run/" ~ id, icon_name="play")`. `<div id="blocks">` contains
`partials/routine_blocks.html`:
```jinja
{% call ui.section("Blocks", footer=total_minutes ~ " min in total") %}
  {% call ui.group() %}
    {% for b in blocks %}
      {% call ui.row(b.title, sub=b.minutes ~ " min" ~ (" · " ~ b.bpm ~ " bpm" if b.bpm else ""), chevron_=False) %}
        {{ ui.button("Up", size="small", attrs={"hx-post": base ~ "/blocks/" ~ b.id ~ "/move?direction=up", "hx-target": "#blocks", "aria-label": "Move " ~ b.title ~ " up"}) }}
        {{ ui.button("Down", size="small", attrs={…direction=down…}) }}
        {{ ui.button("Remove", size="small", kind="ghost", attrs={"hx-post": base ~ "/blocks/" ~ b.id ~ "/remove", "hx-target": "#blocks", "aria-label": "Remove " ~ b.title}) }}
      {% endcall %}
    {% endfor %}
  {% endcall %}
{% endcall %}
```
Then section "Add a block": a form (`hx-post …/blocks`, `hx-target="#blocks"`) with a group of
`ui.select("item_id", "Song or exercise", items)`, `ui.field("minutes", "Minutes", 5, type="number")`,
`ui.field("bpm", "BPM (optional)", type="number")` and `ui.button("Add block", kind="primary", type="submit")`.
Last: a group with `ui.row("Delete routine…", href=…, tone="danger")`.

**Runner `/run/{routine_id}` and `/run/item/{id}`** — title "Ready" (JS sets "2 of 4");
nav_left `ui.nav_link("End", "/", back=True)` (JS makes it finish the session).
```jinja
<div class="runner stack-lg" data-blocks="{{ blocks_json }}" data-routine-id="{{ routine_id or '' }}">
  <div class="blocks" id="run-blocks" aria-hidden="true">{% for b in blocks %}<span></span>{% endfor %}</div>
  <div class="runner-head"><p class="runner-title" id="run-title">{{ blocks[0].title }}</p>
    <p class="runner-sub" id="run-sub">{{ next_text }}</p></div>
  <div class="countdown">
    <p class="countdown-time" id="run-time">{{ first_time }}</p>
    <progress class="bar" id="run-bar" value="0" max="1" aria-label="Time used in this block"></progress>
    <p class="countdown-note" id="run-note">of {{ first_time }}</p>
  </div>
  <div class="split">
    <div class="stack">
      <div class="beats" id="run-beats" aria-hidden="true"><span></span><span></span><span></span><span></span></div>
      <div class="actions-split">
        {{ ui.button("+1 min", attrs={"id": "run-plus"}) }}
        {{ ui.button("Start", kind="primary", icon_name="play", attrs={"id": "run-main"}) }}
        {{ ui.button("Skip", icon_name="skip", attrs={"id": "run-skip"}) }}
      </div>
      {% call ui.group(attrs={"id": "run-links"}) %}{# rows: Tab / PDF / Backing track of the current block; JS shows the current block's rows with `hidden` #}{% endcall %}
      {{ ui.button("Record a take", kind="outline-danger", block=True, icon_name="record", attrs={"id": "run-record"}) }}
    </div>
    {% call ui.group() %}
      {% call ui.row("Tempo", chevron_=False) %}{{ ui.stepper("tempo", start_bpm, "run-bpm", steps=(-1, 1)) }}{% endcall %}
      {% call ui.row("", chevron_=False) %}{{ ui.button("−5", size="small", attrs={"data-bpm": "-5", "aria-label": "5 slower"}) }}{{ ui.button("+5", size="small", attrs={"data-bpm": "5", "aria-label": "5 faster"}) }}{{ ui.button("Tap", size="small", attrs={"id": "run-tap"}) }}{% endcall %}
      {% call ui.row("Beats", chevron_=False) %}{{ ui.segmented("beats", "Beats per bar", [(2, "2"), (3, "3"), (4, "4"), (6, "6")], selected=4) }}{% endcall %}
      {{ ui.switch_row("metronome", "Metronome", checked=True, attrs={"id": "run-metronome"}) }}
      {{ ui.range_row("volume", "Volume", 0.7, attrs={"id": "run-volume"}) }}
    {% endcall %}
  </div>
  <div id="run-summary" hidden>{# section "Done" with a group: a row per block (title, minutes, bpm) and a link home #}</div>
</div>
```
`blocks_json` is made in Python with `json.dumps` and passed through Jinja's escaping (never
build JSON in the template). JS sets text, `is-done`/`is-current` on `#run-blocks span`,
`is-on` on the current `#run-beats span` per click, and the `#run-main` label
(Start / Pause / Resume).

**Progress `/progress`** — section "Last 12 weeks": `ui.group(pad=True)` with the SVG (chart
classes; goal line `.chart-goal`) and a `<table class="visually-hidden">` with the same numbers;
`.stats` with `ui.stat` for this week, 12-week average, best week; section "Tempo, last 90 days":
group of rows (title, sub "60 → 84", value "+24 bpm").

**Settings `/settings`** — `<form method="post" class="form stack-lg">`: section "Practice" group with
`ui.field("weekly_goal_minutes", "Weekly goal (minutes)", type="number", hint="0 turns the goal off")`;
section "Look": group with `ui.select("theme", "Theme", [("amp", "Amp"), ("flat", "Flat"), ("daylight", "Daylight")])`;
section "Tuner": group with `ui.field("tuner_a4", "Reference A4 (Hz)", type="number", hint="430–450")`;
actions Save. Then section "More": group with `ui.row("Style guide", href="/styleguide")` and a
logout `<form method="post" action="/logout">` holding a group with `ui.row_button("Log out", tone="danger")`.

**Tuner `/tuner`** (`active="tuner"`)
```jinja
<div class="stack-lg" id="tuner" data-a4="{{ a4 }}">
  <div class="tuner">
    <p class="tuner-note" id="tuner-note">–</p>
    <p class="tuner-hz" id="tuner-hz">&nbsp;</p>
    <div class="tuner-meter is-idle" id="tuner-meter" aria-hidden="true"><span class="tuner-needle"></span></div>
    <div class="tuner-scale" aria-hidden="true"><span>−50</span><span>0</span><span>+50</span></div>
    <p class="tuner-status" id="tuner-status" aria-live="polite">Play a string</p>
  </div>
  {{ ui.button("Start tuner", kind="primary", size="big", block=True, icon_name="mic", attrs={"id": "tuner-toggle"}) }}
  {% call ui.section("Reference tones", footer="Standard tuning, A4 = " ~ a4 ~ " Hz. Change it in Settings.") %}
    <div class="cluster">
      {% for name, freq in strings %}{{ ui.button(name, size="small", attrs={"data-freq": freq, "aria-pressed": "false"}) }}{% endfor %}
    </div>
  {% endcall %}
</div>
```
The note shows the octave as `<sub>`: JS sets `textContent` of the note and of a `<sub>` it
creates, never `innerHTML` with user data. The nearest string gets `aria-pressed="true"`.

**Login** — `{% set bare = True %}`, title "Woodshed". A `<form method="post" class="form stack-lg">`
with a group `ui.field("password", "Password", "", type="password", required=True, error=error)`
and `ui.button("Log in", kind="primary", type="submit", size="big", block=True)`.

**404** — title "Not found"; `ui.empty("Page not found", "That page doesn't exist (any more).", "/", "Go home")`.

## Accessibility (still applies)
Touch targets ≥ 48 px (the macros do this), contrast AA in all three themes (the tokens do
this), visible focus, `prefers-reduced-motion` respected (the tokens set durations to 0),
nothing told by colour alone ("In tune" is also text).
