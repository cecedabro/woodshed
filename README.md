# Woodshed

A self-hosted guitar practice organiser. It doesn't listen or score: it gives your practice
structure and keeps the log. Routines of timed blocks with a built-in metronome that move on by
themselves, a library of songs and exercises with your own tabs (Guitar Pro / MusicXML via
alphaTab, PDF) and backing tracks, tempo progress per piece, recorded takes to compare, and a
weekly goal. No streaks.

Runs on a k3s homelab as a home-screen web app (`https://guitar.home.cedricschippers.dev`).

Built incrementally by a local coding agent. If you are that agent, start with `AGENTS.md`.
If you are a human: requirements are in `SPEC.md`, the task list in `PLAN.md`.

## Quick start (human)
```bash
make setup && make check
```
Try the production image locally: [docs/docker-local.md](docs/docker-local.md).

## Licence
MIT (see `LICENSE`). Vendored: alphaTab (MPL-2.0), htmx (0BSD), Bravura font (OFL).
