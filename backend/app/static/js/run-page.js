// Run page glue: wires runner.js and the Metronome to run.html (docs/design.md runner recipe).
// Decisions about what to show live in runner-view.js (pure, tested); this file only applies them.

import { createRunner } from "./runner.js";
import { createRecorder } from "./recorder.js";
import { clampBpm, Metronome, tapTempo } from "./metronome.js";
import { beatIndex, formatTime, linksHidden, runnerView } from "./runner-view.js";

const $ = (sel) => document.querySelector(sel);
const $$ = (sel) => [...document.querySelectorAll(sel)];

// --- Metronome preferences (SPEC 6.3) ---

const LS_VOLUME = "woodshed_metronome_volume";
const LS_ON = "woodshed_metronome_on";

function loadPrefs() {
  let volume = 0.7;
  let on = true;
  try {
    const v = parseFloat(localStorage.getItem(LS_VOLUME));
    if (!Number.isNaN(v)) volume = Math.max(0, Math.min(1, v));
    const o = localStorage.getItem(LS_ON);
    if (o !== null) on = o === "true";
  } catch (_) { /* storage unavailable */ }
  return { volume, on };
}

function savePrefs() {
  try {
    localStorage.setItem(LS_VOLUME, String(volume));
    localStorage.setItem(LS_ON, String(metronomeOn));
  } catch (_) { /* storage unavailable */ }
}

// --- Wake lock (SPEC 5.9) ---

let wakeLock = null;
async function requestWakeLock() {
  try {
    if ("wakeLock" in navigator) wakeLock = await navigator.wakeLock.request("screen");
  } catch (_) { /* not supported or refused */ }
}
function releaseWakeLock() {
  if (wakeLock) wakeLock.release().catch(() => {});
  wakeLock = null;
}
document.addEventListener("visibilitychange", () => {
  if (!document.hidden && running) requestWakeLock();
});

// --- API (SPEC 5.4). Calls run one after another, so "finish" never overtakes a block. ---

let apiQueue = Promise.resolve();
function queued(fn) {
  const next = apiQueue.then(fn, fn);
  apiQueue = next.catch(() => {});
  return next;
}

let sessionId = null;

async function postJson(url, body) {
  const res = await fetch(url, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: body === undefined ? undefined : JSON.stringify(body),
  });
  if (!res.ok) throw new Error(`${url}: ${res.status}`);
  return res.json();
}

const api = {
  startSession: () =>
    queued(async () => {
      const result = await postJson("/api/sessions", { routine_id: routineId });
      sessionId = result.id;
      return result.id;
    }),
  logBlock: (sid, data) => queued(() => postJson(`/api/sessions/${sid}/blocks`, data)),
  finish: (sid) =>
    queued(() => postJson(`/api/sessions/${sid}/finish`)).then(showSummary, () => showSummary(null)),
};

// --- Page state ---

const runnerEl = $(".runner");
const blocks = JSON.parse(runnerEl.dataset.blocks || "[]");
const routineId = /^\d+$/.test(runnerEl.dataset.routineId || "")
  ? parseInt(runnerEl.dataset.routineId, 10)
  : null;

const el = {
  navTitle: $(".navbar-title"),
  end: $(".navbar-left a"),
  blocks: $$("#run-blocks span"),
  title: $("#run-title"),
  sub: $("#run-sub"),
  time: $("#run-time"),
  bar: $("#run-bar"),
  note: $("#run-note"),
  beats: $("#run-beats"),
  main: $("#run-main"),
  plus: $("#run-plus"),
  skip: $("#run-skip"),
  links: $$("#run-links [data-block]"),
  bpm: $("#run-bpm"),
  tap: $("#run-tap"),
  metronome: $("#run-metronome"),
  volume: $("#run-volume"),
  summary: $("#run-summary"),
  record: $("#run-record"),
  timer: $("#run-timer"),
  icons: [...($("#run-icons")?.content.children || [])], // [play, pause]
};

const prefs = loadPrefs();
let volume = prefs.volume;
let metronomeOn = prefs.on;
let beatsPerBar = parseInt($('input[name="beats"]:checked')?.value || "4", 10);
let bpm = blocks[0]?.start_bpm ?? 80;
let started = false;
let running = false;
let finished = false;
let shownIndex = 0;
let taps = [];
let tickTimer = null;
let audioCtx = null;
let metronome = null;
let clicking = false;

const runner = createRunner(blocks, {
  api,
  now: () => Date.now(),
  cue: () => metronome?.playCue(),
  bpmToLog: (b) => (metronomeOn ? b : null),
});

// --- Recorder (SPEC 8.1) ---

const recorder = createRecorder({
  element: runnerEl,
  itemId: blocks[0]?.item_id ?? 0,
  bpm: () => bpm,
  sessionBlockId: () => sessionId,
  onStart: () => {
    if (el.timer) el.timer.hidden = false;
  },
  onStop: () => {
    if (el.timer) el.timer.hidden = true;
  },
  onUpload: () => {
    if (el.timer) el.timer.hidden = true;
  },
  onRecordingError: (msg) => {
    alert(msg);
  },
});

// --- Rendering ---

function setText(node, text) {
  if (node && node.textContent !== text) node.textContent = text;
}

function render() {
  if (finished) return;
  const state = runner.current();
  const index = started ? state.index : 0;
  const remaining = started ? state.remaining : (blocks[0]?.planned_seconds ?? 0);
  const view = runnerView({ started, index, paused: state.paused, remaining }, blocks, beatsPerBar);
  el.blocks.forEach((span, i) => { span.className = view.blocks[i] || ""; });
  setText(el.navTitle, view.title);
  setText(el.main?.querySelector("span"), view.main);
  const icon = view.main === "Pause" ? el.icons[1] : el.icons[0];
  const svg = el.main?.querySelector("svg");
  if (icon && svg && !svg.isEqualNode(icon)) svg.replaceWith(icon.cloneNode(true));
  setText(el.title, view.blockTitle);
  setText(el.sub, view.next);
  setText(el.time, view.time);
  setText(el.note, view.of);
  if (el.bar) el.bar.value = view.used;
  const hidden = linksHidden(el.links.map((a) => parseInt(a.dataset.block, 10)), index);
  el.links.forEach((a, i) => { a.hidden = hidden[i]; });
  setText(el.bpm, String(bpm));
}

function renderBeatDots() {
  if (!el.beats) return;
  el.beats.replaceChildren(
    ...Array.from({ length: beatsPerBar }, () => document.createElement("span")),
  );
}

function lightBeat(beat, timeMs) {
  if (!el.beats) return;
  // Beats are scheduled ahead; light the dot when the click is actually heard.
  const delay = Math.max(0, timeMs - audioCtx.currentTime * 1000);
  setTimeout(() => {
    if (!clicking) return;
    const on = beatIndex(beat, beatsPerBar);
    [...el.beats.children].forEach((s, i) => s.classList.toggle("is-on", i === on));
  }, delay);
}

// --- Metronome ---

function ensureMetronome() {
  if (metronome) return;
  const Ctx = window.AudioContext || window.webkitAudioContext;
  audioCtx = new Ctx();
  metronome = new Metronome(audioCtx);
  metronome.setVolume(volume);
  metronome.setBeatsPerBar(beatsPerBar);
  metronome.onBeat(({ beat, time }) => lightBeat(beat, time));
}

function syncMetronome() {
  if (!metronome) return;
  const shouldClick = running && metronomeOn && !runner.current().paused;
  if (shouldClick && !clicking) metronome.start(bpm);
  if (!shouldClick && clicking) {
    metronome.stop();
    [...(el.beats?.children || [])].forEach((s) => s.classList.remove("is-on"));
  }
  clicking = shouldClick;
}

function setBpm(next) {
  bpm = clampBpm(next);
  runner.setBpm(bpm);
  if (clicking) metronome.setBpm(bpm);
  render();
}

// --- Session flow ---

function tick() {
  runner.tick();
  const state = runner.current();
  if (state.index === null) {
    stop();
    return;
  }
  if (state.index !== shownIndex) {
    // A new block started with its own start BPM.
    shownIndex = state.index;
    bpm = blocks[shownIndex].start_bpm ?? 80;
    runner.setBpm(bpm);
    if (clicking) metronome.setBpm(bpm);
  }
  render();
}

function start() {
  started = true;
  running = true;
  ensureMetronome();
  runner.start();
  runner.setBpm(bpm);
  requestWakeLock();
  tickTimer = setInterval(tick, 250);
  syncMetronome();
  render();
}

function stop() {
  running = false;
  if (tickTimer) clearInterval(tickTimer);
  tickTimer = null;
  syncMetronome();
  releaseWakeLock();
  recorder?.stop();
}

function showSummary(summary) {
  stop();
  finished = true;
  if (!el.summary) return;
  const row = (title, sub, value, href) => {
    const r = document.createElement(href ? "a" : "div");
    r.className = "row";
    if (href) r.href = href;
    const main = document.createElement("span");
    main.className = "row-main";
    const t = document.createElement("span");
    t.className = "row-title";
    t.textContent = title;
    main.append(t);
    if (sub) {
      const s = document.createElement("span");
      s.className = "row-sub";
      s.textContent = sub;
      main.append(s);
    }
    r.append(main);
    if (value) {
      const v = document.createElement("span");
      v.className = "row-value";
      v.textContent = value;
      r.append(v);
    }
    return r;
  };
  const section = document.createElement("section");
  section.className = "section";
  const header = document.createElement("h2");
  header.className = "section-header";
  header.textContent = "Done";
  const group = document.createElement("div");
  group.className = "group";
  for (const b of summary?.per_block || []) {
    group.append(row(b.item_title, formatTime(b.played_seconds), b.bpm != null ? `${b.bpm} bpm` : "—"));
  }
  group.append(row("Back home", null, null, "/"));
  const footer = document.createElement("p");
  footer.className = "section-footer";
  footer.textContent = summary ? `${summary.minutes} min in total` : "Could not load the summary.";
  section.append(header, group, footer);
  el.summary.replaceChildren(section);
  for (const child of runnerEl.children) child.hidden = child !== el.summary;
  el.summary.hidden = false;
  setText(el.navTitle, "Done");
}

// --- Controls ---

el.main?.addEventListener("click", () => {
  if (!started) start();
  else if (runner.current().paused) runner.resume();
  else runner.pause();
  syncMetronome();
  render();
});
el.plus?.addEventListener("click", () => {
  runner.addMinute();
  render();
});
el.skip?.addEventListener("click", () => {
  if (!started || finished) return;
  runner.skip();
  tick();
});
el.end?.addEventListener("click", (event) => {
  if (!started || finished) return; // not started yet: just leave
  event.preventDefault();
  runner.finish(); // logs the block in progress; api.finish then shows the summary
  stop();
});

for (const btn of $$('[data-for="run-bpm"]')) {
  btn.addEventListener("click", () => setBpm(bpm + parseInt(btn.dataset.step, 10)));
}
for (const btn of $$("[data-bpm]")) {
  btn.addEventListener("click", () => setBpm(bpm + parseInt(btn.dataset.bpm, 10)));
}
el.tap?.addEventListener("click", () => {
  taps = [...taps.slice(-7), Date.now()];
  const tapped = tapTempo(taps);
  if (tapped !== null) setBpm(tapped);
});
for (const radio of $$('input[name="beats"]')) {
  radio.addEventListener("change", () => {
    beatsPerBar = parseInt(radio.value, 10);
    metronome?.setBeatsPerBar(beatsPerBar);
    renderBeatDots();
  });
}
el.metronome?.addEventListener("change", () => {
  metronomeOn = el.metronome.checked;
  savePrefs();
  syncMetronome();
});
el.volume?.addEventListener("input", () => {
  volume = parseFloat(el.volume.value);
  savePrefs();
  metronome?.setVolume(volume);
});

// --- Boot ---

if (el.metronome) el.metronome.checked = metronomeOn;
if (el.volume) el.volume.value = String(volume);
renderBeatDots();
render();
