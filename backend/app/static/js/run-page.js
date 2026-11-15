// Run-page glue module — wires runner.js + Metronome to the DOM.
// Loads as `<script type="module">` from run.html.

import { createRunner } from "./runner.js";
import { clampBpm, Metronome } from "./metronome.js";

// --- localStorage keys (SPEC 6.3) ---

const LS_VOLUME = "woodshed_metronome_volume";
const LS_ON = "woodshed_metronome_on";

function loadMetronomePrefs() {
  let volume = 0.5;
  let on = true;
  try {
    const v = localStorage.getItem(LS_VOLUME);
    if (v !== null) volume = Math.max(0, Math.min(1, parseFloat(v) || 0.5));
    const o = localStorage.getItem(LS_ON);
    if (o !== null) on = o === "true";
  } catch (_) { /* storage unavailable */ }
  return { volume, on };
}

function saveMetronomePrefs(volume, on) {
  try {
    localStorage.setItem(LS_VOLUME, String(volume));
    localStorage.setItem(LS_ON, String(on));
  } catch (_) { /* storage unavailable */ }
}

// --- DOM helpers ---

function $(sel) {
  return document.querySelector(sel);
}

function $$(sel) {
  return document.querySelectorAll(sel);
}

function formatTime(ms) {
  const totalSeconds = Math.max(0, Math.ceil(ms / 1000));
  const m = Math.floor(totalSeconds / 60);
  const s = totalSeconds % 60;
  return `${m}:${String(s).padStart(2, "0")}`;
}

// --- Wake lock (SPEC 5.9) ---

let wakeLock = null;

async function requestWakeLock() {
  try {
    if ("wakeLock" in navigator) {
      wakeLock = await navigator.wakeLock.request("screen");
    }
  } catch (_) { /* wake lock not supported */ }
}

function releaseWakeLock() {
  if (wakeLock) {
    wakeLock.release().catch(() => {});
    wakeLock = null;
  }
}

// Restore wake lock on visibility change
document.addEventListener("visibilitychange", async () => {
  if (!document.hidden && wakeLocking) {
    await requestWakeLock();
  }
});

let wakeLocking = false;

// --- API helpers ---

async function startSessionApi() {
  const res = await fetch("/api/sessions", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ routine_id: parseInt(runnerEl.dataset.routineId || "0", 10) }),
  });
  if (!res.ok) throw new Error("Failed to start session");
  const data = await res.json();
  return data.id;
}

async function logBlockApi(sessionId, data) {
  await fetch(`/api/sessions/${sessionId}/blocks`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(data),
  });
}

async function finishApi(sessionId) {
  const res = await fetch(`/api/sessions/${sessionId}/finish`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
  });
  if (!res.ok) throw new Error("Failed to finish session");
  return res.json();
}

// --- Init ---

const runnerEl = $(".runner");
if (!runnerEl) throw new Error("No .runner element found");

const blocksData = JSON.parse(runnerEl.dataset.blocks || "[]");
const routineName = runnerEl.querySelector("h1")?.textContent || "Session";

// --- State ---

const { volume: defaultVolume, on: defaultOn } = loadMetronomePrefs();
let metronomeOn = defaultOn;
let currentVolume = defaultVolume;
let beatsPerBar = 4;
let sessionSummary = null;
let runner = null;
let metronome = null;
let tickInterval = null;
let tapTaps = [];
let sessionId = null;

// --- DOM element references ---

let timerDisplay = null;
let bpmDisplay = null;
let currentBlockTitle = null;
let bpmMinus5Btn = null;
let bpmMinus1Btn = null;
let bpmPlus1Btn = null;
let bpmPlus5Btn = null;
let tapTempoBtn = null;
let beatsPerBarSelect = null;
let metronomeToggleBtn = null;
let volumeSlider = null;
let summaryEl = null;

function findDomElements() {
  timerDisplay = $(".timer-display") || $(".block-timer");
  bpmDisplay = $(".bpm-display") || $(".block-bpm-display");
  currentBlockTitle = $(".current-block-title");
  bpmMinus5Btn = $("#bpm-minus-5");
  bpmMinus1Btn = $("#bpm-minus-1");
  bpmPlus1Btn = $("#bpm-plus-1");
  bpmPlus5Btn = $("#bpm-plus-5");
  tapTempoBtn = $("#tap-tempo");
  beatsPerBarSelect = $("#beats-per-bar");
  metronomeToggleBtn = $("#metronome-toggle");
  volumeSlider = $("#metronome-volume");
  summaryEl = $(".session-summary");
}

// --- Summary view ---

function showSummary(summary) {
  if (!summaryEl) return;
  sessionSummary = summary;

  const rows = [];
  for (const block of summary.blocks || []) {
    const mins = (block.played_seconds / 60).toFixed(1);
    const bpmStr = block.bpm != null ? `${block.bpm} BPM` : "—";
    rows.push(`<tr><td>${block.title}</td><td>${mins} min</td><td>${bpmStr}</td></tr>`);
  }

  const totalMins = summary.total_minutes != null ? summary.total_minutes.toFixed(1) : "0";
  summaryEl.innerHTML = `
    <h2>Session complete</h2>
    <table class="summary-table">
      <thead><tr><th>Block</th><th>Played</th><th>BPM</th></tr></thead>
      <tbody>${rows.join("")}</tbody>
    </table>
    <p class="summary-total">Total: ${totalMins} min</p>
    <a href="/" class="btn">Back home</a>
  `;
  summaryEl.style.display = "block";
  if (runnerEl) runnerEl.style.display = "none";
}

// --- Runner initialisation ---

function initRunner() {
  const deps = {
    api: {
      startSession: startSessionApi,
      logBlock: logBlockApi,
      finish: finishApi,
    },
    now: () => Date.now(),
    cue: () => {
      if (metronome && metronomeOn) {
        metronome.playCue();
      }
    },
  };

  runner = createRunner(blocksData, deps);
}

// --- Metronome initialisation ---

function initMetronome() {
  const ctx = new (window.AudioContext || window.webkitAudioContext)();
  metronome = new Metronome(ctx);
  metronome.setVolume(currentVolume);
  metronome.setBeatsPerBar(beatsPerBar);
}

// --- Countdown update ---

function updateCountdown() {
  if (!timerDisplay || !runner) return;
  const state = runner.current();
  timerDisplay.textContent = formatTime(state.remaining);
}

function updateBpmDisplay() {
  if (!bpmDisplay || !runner) return;
  const state = runner.current();
  bpmDisplay.textContent = `${state.bpm} BPM`;
}

// --- Tap tempo ---

function handleTapTempo() {
  const now = Date.now();
  tapTaps.push(now);

  // Remove taps older than 2 seconds from each other
  // (tapTempo handles the gap filtering)
  const bpm = tapTempo(tapTaps);
  if (bpm !== null && runner) {
    runner.setBpm(bpm);
    updateBpmDisplay();
  }
}

// --- BPM buttons ---

function handleBpmChange(delta) {
  if (!runner) return;
  const state = runner.current();
  const newBpm = clampBpm(state.bpm + delta);
  runner.setBpm(newBpm);
  updateBpmDisplay();
}

// --- Beat per bar ---

function handleBeatsPerBarChange() {
  if (!beatsPerBarSelect) return;
  beatsPerBar = parseInt(beatsPerBarSelect.value, 10) || 4;
  if (metronome) {
    metronome.setBeatsPerBar(beatsPerBar);
  }
}

// --- Metronome on/off ---

function toggleMetronome() {
  metronomeOn = !metronomeOn;
  saveMetronomePrefs(currentVolume, metronomeOn);
  if (metronomeToggleBtn) {
    metronomeToggleBtn.textContent = metronomeOn ? "Metronome: ON" : "Metronome: OFF";
  }
  if (!metronomeOn && metronome) {
    metronome.stop();
  } else if (metronomeOn && metronome && runner && runner.current().done !== true) {
    const state = runner.current();
    if (state.index !== null && !state.done) {
      const bpm = state.bpm || 80;
      metronome.start(bpm);
    }
  }
}

// --- Volume ---

function handleVolumeChange() {
  if (!volumeSlider) return;
  currentVolume = parseFloat(volumeSlider.value);
  saveMetronomePrefs(currentVolume, metronomeOn);
  if (metronome) {
    metronome.setVolume(currentVolume);
  }
}

// --- Start the session ---

function startSession() {
  if (runner) return; // already running

  initRunner();
  initMetronome();

  wakeLocking = true;
  requestWakeLock();

  // Start runner
  runner.start();
  sessionId = runner.current().index !== null ? null : null;

  // Start metronome for first block
  if (metronomeOn) {
    const state = runner.current();
    const bpm = state.bpm || 80;
    metronome.start(bpm);
  }

  // Start tick interval (250 ms)
  tickInterval = setInterval(() => {
    if (!runner) return;

    const state = runner.current();

    // Update countdown
    updateCountdown();
    updateBpmDisplay();

    // Update metronome BPM if changed
    if (metronome && state.bpm !== undefined) {
      metronome.setBpm(state.bpm || 80);
    }

    // Update current block title
    if (currentBlockTitle && state.title) {
      currentBlockTitle.textContent = state.title;
    }

    // Update beats per bar select
    if (beatsPerBarSelect) {
      beatsPerBarSelect.value = String(beatsPerBar);
    }

    // Update metronome toggle
    if (metronomeToggleBtn) {
      metronomeToggleBtn.textContent = metronomeOn ? "Metronome: ON" : "Metronome: OFF";
    }

    // Update volume slider
    if (volumeSlider) {
      volumeSlider.value = String(currentVolume);
    }

    // Tick the runner
    runner.tick();

    // Check if session is done
    const afterState = runner.current();
    if (afterState.done && afterState.index === null) {
      stopSession();
    }
  }, 250);
}

function stopSession() {
  if (tickInterval) {
    clearInterval(tickInterval);
    tickInterval = null;
  }
  if (metronome) {
    metronome.stop();
  }
  releaseWakeLock();
  wakeLocking = false;
}

// --- Wire up block controls ---

function wireBlockControls() {
  const actions = runnerEl.querySelectorAll("[data-action]");
  for (const btn of actions) {
    const action = btn.dataset.action;

    btn.addEventListener("click", () => {
      if (action === "start") {
        startSession();
      } else if (action === "pause") {
        if (runner) runner.pause();
      } else if (action === "skip") {
        if (runner) runner.skip();
      }
    });
  }
}

// --- Wire up global controls ---

function wireGlobalControls() {
  if (bpmMinus5Btn) {
    bpmMinus5Btn.addEventListener("click", () => handleBpmChange(-5));
  }
  if (bpmMinus1Btn) {
    bpmMinus1Btn.addEventListener("click", () => handleBpmChange(-1));
  }
  if (bpmPlus1Btn) {
    bpmPlus1Btn.addEventListener("click", () => handleBpmChange(1));
  }
  if (bpmPlus5Btn) {
    bpmPlus5Btn.addEventListener("click", () => handleBpmChange(5));
  }
  if (tapTempoBtn) {
    tapTempoBtn.addEventListener("click", handleTapTempo);
  }
  if (beatsPerBarSelect) {
    beatsPerBarSelect.addEventListener("change", handleBeatsPerBarChange);
  }
  if (metronomeToggleBtn) {
    metronomeToggleBtn.addEventListener("click", toggleMetronome);
  }
  if (volumeSlider) {
    volumeSlider.addEventListener("input", handleVolumeChange);
  }
}

// --- Boot ---

findDomElements();
wireBlockControls();
wireGlobalControls();

// Set initial control states from localStorage
if (metronomeToggleBtn) {
  metronomeToggleBtn.textContent = metronomeOn ? "Metronome: ON" : "Metronome: OFF";
}
if (volumeSlider) {
  volumeSlider.value = String(currentVolume);
}
if (beatsPerBarSelect) {
  beatsPerBarSelect.value = String(beatsPerBar);
}
