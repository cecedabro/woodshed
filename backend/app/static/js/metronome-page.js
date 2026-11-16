// Metronome page glue: wires T90 markup to Metronome class.

import { clampBpm, Metronome, tapTempo } from "./metronome.js";
import { beatIndex } from "./runner-view.js";
import { loadPrefs, savePrefs } from "./metronome-prefs.js";

const $ = (sel) => document.querySelector(sel);

// --- State ---

let prefs = loadPrefs(localStorage);
let bpm = prefs.bpm;
let beatsPerBar = prefs.beats;
let volume = prefs.volume;
let metronome = null;
let audioCtx = null;
let running = false;
let taps = [];

const el = {
  start: $("#met-start"),
  bpm: $("#met-bpm"),
  tap: $("#met-tap"),
  volume: $("#met-volume"),
  beats: $("#met-beats"),
  beatsInput: document.querySelector('input[name="beats"]:checked'),
};

// --- Beat dots ---

function rebuildBeatDots() {
  if (!el.beats) return;
  el.beats.replaceChildren(
    ...Array.from({ length: beatsPerBar }, () => document.createElement("span")),
  );
}

function highlightCurrentBeat(beat) {
  if (!el.beats) return;
  const on = beatIndex(beat, beatsPerBar);
  [...el.beats.children].forEach((s, i) => s.classList.toggle("is-on", i === on));
}

// --- Metronome ---

function ensureMetronome() {
  if (metronome) return;
  const Ctx = window.AudioContext || window.webkitAudioContext;
  audioCtx = new Ctx();
  metronome = new Metronome(audioCtx);
  metronome.setVolume(volume);
  metronome.setBeatsPerBar(beatsPerBar);
  metronome.onBeat(({ beat }) => highlightCurrentBeat(beat));
}

function syncMetronome() {
  if (!metronome) return;
  if (running) {
    metronome.start(bpm);
  } else {
    metronome.stop();
    highlightCurrentBeat(0);
  }
}

// --- UI sync ---

function syncUI() {
  if (el.bpm) el.bpm.textContent = String(bpm);
  if (el.start) el.start.textContent = running ? "Stop" : "Start";
}

function syncPrefs() {
  savePrefs(localStorage, { volume, bpm, beats: beatsPerBar });
}

// --- BPM ---

function setBpm(next) {
  bpm = clampBpm(next);
  if (running && metronome) metronome.setBpm(bpm);
  syncUI();
}

// --- Tap tempo ---

function handleTap() {
  const now = Date.now();
  taps = [...taps.slice(-7), now];
  if (now - taps[0] > 10000) taps = [now];
  const tapped = tapTempo(taps);
  if (tapped !== null) setBpm(tapped);
}

// --- Start / Stop ---

function startMetronome() {
  ensureMetronome();
  running = true;
  metronome.start(bpm);
  syncUI();
}

function stopMetronome() {
  running = false;
  metronome.stop();
  highlightCurrentBeat(0);
  syncUI();
}

// --- Beats selector ---

function handleBeatsChange(value) {
  beatsPerBar = value;
  if (running && metronome) metronome.setBeatsPerBar(beatsPerBar);
  rebuildBeatDots();
  syncPrefs();
}

// --- Event listeners ---

el.start?.addEventListener("click", () => {
  if (running) stopMetronome();
  else startMetronome();
});

document.querySelectorAll('[data-bpm]').forEach((btn) => {
  btn.addEventListener("click", () => {
    setBpm(bpm + parseInt(btn.dataset.bpm, 10));
  });
});

el.tap?.addEventListener("click", handleTap);

el.volume?.addEventListener("input", () => {
  volume = parseFloat(el.volume.value);
  syncPrefs();
  if (metronome) metronome.setVolume(volume);
});

document.querySelectorAll('input[name="beats"]').forEach((radio) => {
  radio.addEventListener("change", () => {
    handleBeatsChange(parseInt(radio.value, 10));
  });
});

// --- Boot ---

rebuildBeatDots();
syncUI();
