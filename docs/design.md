# Design brief

You own the visual design. This brief sets the mood and the hard constraints.

## Mood
A practice room, not a dashboard: warm, dark and calm. Think a valve amp at night:
near-black brown background, cream text, one warm accent (amber, like a pilot light) and
one secondary (a muted teal) for progress. Plenty of space, big type, few borders.
Light mode is optional; dark is the default (`color-scheme: dark`).

## Hard constraints
- One stylesheet `static/style.css` with design tokens as CSS custom properties at the top
  (colours, spacing, radii, font sizes). Pages use the tokens, not raw values.
- System font stack (no web fonts except alphaTab's Bravura). Timer digits use
  `font-variant-numeric: tabular-nums` so they don't jump.
- Mobile first: works at 360 px wide without horizontal scroll; at ≥ 768 px (iPad) the
  runner uses the width: big timer, BPM and current item readable from 1.5 m on a music stand.
- Touch targets ≥ 48 × 48 px; the primary action on each screen is obvious and large
  (home: start the routine; runner: pause/resume).
- Contrast at least WCAG AA. Focus outlines visible.
- Respect `prefers-reduced-motion`; no animation is needed to understand anything.
- Progress is shown calmly: a week bar and numbers. No streak counters, flames, badges or nagging.

## Screens in one line each
- Home: this week's bar ("75 of 120 min"), then the routines as big buttons.
- Runner: current item title, huge countdown, BPM with −5/−1/+1/+5 and tap, next block preview,
  pause/skip/+1 min/finish, links to the tab/PDF/backing track, record button.
- Library: grouped by status, search on top. Item page: notes, files, takes, tempo history.
