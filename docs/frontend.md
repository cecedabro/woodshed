# Frontend

Server-rendered Jinja2 pages with HTMX, served by the FastAPI app. No SPA, no build step,
no npm packages. Look and feel: `docs/design.md`.

## Rules
- Templates in `backend/app/templates/`, all extending `base.html` and built from the
  `_ui.html` macros (docs/design.md; `tests/test_ui_rules.py` checks). Static files in
  `backend/app/static/` (mounted at `/static`). Pages must render useful content without JS;
  JS adds the timer, metronome, recorder and tab rendering.
- No inline `<script>` and no `on*=` attributes (the CSP forbids them). Pass data to JS with
  `data-*` attributes (JSON in a `data-` attribute is fine, escaped by Jinja).
- HTMX for partial updates (routine editor, notes, take notes). Forms work as plain POSTs
  too where practical (POST → 303 redirect → GET).
- Every control has a `<label>`; buttons are real `<button>`s; touch targets ≥ 48 px.

## §vendor
Vendored by hand (the agent cannot download): `static/vendor/htmx.min.js` (2.0.11) and
`static/vendor/alphatab/` (alphaTab 1.9.0: `alphaTab.min.js`, `font/Bravura.woff2|woff`,
licences). Do not add or edit vendored files.

## §js
Browser code is ES modules in `static/js/`, loaded with `<script type="module" src=...>`.
Split every feature into a **pure module** (no DOM, no `window`, no real clock or audio;
all inputs are arguments) and a **glue module** (reads the DOM, wires events, calls the pure one).
Pure modules are unit-tested in `backend/tests/js/<name>.test.js` with `node:test` and
`node:assert/strict`. Time is always passed in as milliseconds (`now`), so tests never sleep.

Module contracts (names fixed; later tasks build on them):

`timer.js` — countdown for one block.
```js
export function createTimer(plannedSeconds)   // state: not started
// methods: start(now), pause(now), resume(now), addSeconds(n),
// remaining(now) -> seconds left (>= 0, float), played(now) -> seconds counted while running,
// isDone(now) -> remaining(now) === 0, isRunning() -> bool
```
Paused time is not played time. `addSeconds(60)` is the "+1 min" button.
**Units:** `now` is milliseconds (`Date.now()`), `plannedSeconds`, `remaining()` and `played()`
are seconds. So `t.start(1_000_000); t.remaining(1_001_000) === 59` for a 60 s block. Tests use
realistic millisecond values like these, never small numbers that hide a unit mix-up.

`metronome.js` — scheduling maths plus a thin audio wrapper.
```js
export function clampBpm(bpm)                        // round, clamp to 20..400
export function beatTimes(startTime, bpm, beatsPerBar, fromBeat, untilTime)
// -> [{time, beat, accent}] for every beat index >= fromBeat with time < untilTime;
//    beat k is at startTime + k*60/bpm; accent when k % beatsPerBar === 0
export function tapTempo(tapsMs)                     // -> bpm from the last 4 taps, or null;
//    taps more than 2000 ms apart restart the sequence
export class Metronome { constructor(audioContext) ... start(bpm), stop(), setBpm(bpm), setBeatsPerBar(n), setVolume(v) }
```
The `Metronome` class uses the standard look-ahead pattern: a 25 ms `setInterval` asks
`beatTimes` for beats in the next 100 ms and schedules short oscillator clicks at those exact
`audioContext.currentTime` values (1000 Hz accent, 800 Hz other beats, 30 ms). Create or
`resume()` the `AudioContext` inside a click handler (iOS needs a user gesture).
`start(bpm)` stores `startTime = ctx.currentTime * 1000 + 50` once; every tick calls
`beatTimes(startTime, bpm, beatsPerBar, nextBeat, now + 100)` with that same `startTime`, so
beat k stays at `startTime + k·60000/bpm`. `setBpm` restarts the count: new `startTime` = the
time of the next unscheduled beat, `nextBeat = 0`. `onBeat(callback)` lets the glue light
`.beats` (called with `{beat, accent}` from the tick that schedules it).

`runner.js` — the session runner logic, pure.
```js
export function createRunner(blocks, deps)
// blocks: [{item_id, title, planned_seconds, start_bpm}] ; deps: {api, now, cue}
// api.startSession() -> Promise<id>; api.logBlock(id, payload); api.finish(id) -> Promise<summary>
// methods: start(), tick() (called every 250 ms by the glue), pause(), resume(), skip(),
// addMinute(), setBpm(bpm), finish(), current() -> {index, title, remaining, bpm, paused, done}
```
On `tick()` when the current timer is done: call `deps.cue()`, log the block
(`{item_id, position, planned_seconds, played_seconds, bpm}`; `played_seconds` is a whole
number), start the next block's timer at that block's `start_bpm`. The server builds
`start_bpm` (block BPM, else the item's `current_bpm`, else 80) and the `data-blocks` JSON with
`json.dumps`; the browser never decides the start BPM.
`skip()` logs the block with what was played so far. After the last block, `finish()` runs
automatically. The glue (`run-page.js`) owns the DOM, the `Metronome`, the wake lock
(`navigator.wakeLock?.request("screen")`, re-requested on `visibilitychange`) and `fetch`.

`recorder.js` — `export function pickMimeType(isTypeSupported)` returns the first supported of
`audio/webm;codecs=opus`, `audio/mp4`, `audio/ogg;codecs=opus`, or `""`. The glue records with
`MediaRecorder`, stops after 600 s, and uploads with `FormData` to `/api/items/{id}/takes`.

`pitch.js` — tuner maths, pure (SPEC 13).
```js
export function detectPitch(samples, sampleRate)   // Float32Array -> Hz (float) or null
export function noteFor(freq, a4 = 440)            // -> {name: "A", octave: 2, cents: -3.1, midi: 45}
export const STANDARD = [["E2", 82.41], ["A2", 110.0], ["D3", 146.83], ["G3", 196.0], ["B3", 246.94], ["E4", 329.63]]
export function nearestString(freq)               // -> index into STANDARD
```
`detectPitch`: RMS < 0.01 → null. Autocorrelation over lags for 60–1200 Hz
(`sampleRate/1200 … sampleRate/60`), normalised; take the first peak above 0.9 × the best
(this avoids octave errors), refine with parabolic interpolation, return `sampleRate / lag`.
Names use sharps: C C# D D# E F F# G G# A A# B; `midi = round(69 + 12·log2(f/a4))`,
`cents = 1200·log2(f / (a4·2^((midi−69)/12)))`. `tuner.js` (glue): `getUserMedia({audio:
{echoCancellation: false, noiseSuppression: false, autoGainControl: false}})`, an
`AnalyserNode` with `fftSize = 4096`, read `getFloatTimeDomainData` at most 15 times a second
(requestAnimationFrame + time check), smooth the frequency over the last 3 readings, set the
`--cents` property on `#tuner-meter`, toggle `is-in-tune` (|cents| ≤ 5) and `is-idle`
(null pitch). Reference tones: an `OscillatorNode` (sine) for 2 s with a 50 ms fade in/out.
Stop: stop all tracks, close the context; also on `visibilitychange` to hidden.

## §alphatab (SPEC 3.6)
Tab page: `<div id="tab" data-file="/media/attachment/{id}">`, then
`<script src="/static/vendor/alphatab/alphaTab.min.js">` (classic script, defines global
`alphaTab`) and `<script type="module" src="/static/js/tab.js">`. In `tab.js`:
```js
const el = document.getElementById("tab");
const api = new alphaTab.AlphaTabApi(el, {
  core: { fontDirectory: "/static/vendor/alphatab/font/", useWorkers: false },
  player: { enablePlayer: false },
});
const res = await fetch(el.dataset.file);
api.load(new Uint8Array(await res.arrayBuffer()));
```
Verified to work under the app's CSP. Do **not** use `core.file` (it did not load in testing)
and keep `useWorkers: false` (workers clash with the CSP). Show a friendly message from
`api.error.on(...)`. A small MusicXML file for tests is in `tests/fixtures/sample.musicxml`.

## §pages
`/` home (routine buttons, week progress), `/library`, `/items/{id}` (+ `/new`, `/edit`, `/tab/…`,
`/compare`), `/items/lookup` (fragment), `/routines` (+ editor), `/run/{routine_id}`,
`/run/item/{id}`, `/tuner`, `/progress`, `/settings`, `/styleguide`, `/login`.
Every page follows a recipe in `docs/design.md`.
Route handlers stay thin: they call Python functions that return plain data, and templates only display.

## §pwa (SPEC 10.3)
`/manifest.webmanifest` and `/sw.js` are served from the root (a service worker's scope is its
own path). Icons are PNGs in `static/icons/`, generated once by a stdlib script
(`backend/scripts/make_icons.py`, `zlib` + `struct`) and committed. `base.html` links the
manifest, `apple-touch-icon`, `theme-color`, and `apple-mobile-web-app-capable`.

## Testing
Render pages with the TestClient and assert on the HTML (`html.parser` from the stdlib when
structure matters): expected titles and values, empty states, `data-*` wiring, script tags.
JS logic is tested in node (see §js). Never assert pixel styling.
