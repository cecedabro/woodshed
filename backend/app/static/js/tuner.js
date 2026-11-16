// Tuner glue code.
// SPEC §13, docs/frontend.md §tuner.

import { detectPitch, noteFor, nearestString, STANDARD } from "./pitch.js";

const tuner = document.getElementById("tuner");
const noteEl = document.getElementById("tuner-note");
const hzEl = document.getElementById("tuner-hz");
const meterEl = document.getElementById("tuner-meter");
const needle = meterEl.querySelector(".tuner-needle");
const statusEl = document.getElementById("tuner-status");
const toggleBtn = document.getElementById("tuner-toggle");

const a4 = Number(tuner?.dataset?.a4 ?? 440);

let audioCtx = null;
let analyser = null;
let micStream = null;
let rafId = null;
let playingOsc = null;
let lastTime = 0;
let pitchHistory = [];
const MAX_HISTORY = 3;
const MAX_FPS = 15;

function smoothPitch(raw) {
  if (raw === null) return null;
  pitchHistory.push(raw);
  if (pitchHistory.length > MAX_HISTORY) pitchHistory.shift();
  return pitchHistory.reduce((s, v) => s + v, 0) / pitchHistory.length;
}

function setMeter(cents) {
  tuner?.style.setProperty("--cents", String(cents));
  if (cents === null) {
    meterEl.classList.add("is-idle");
    meterEl.classList.remove("is-in-tune");
  } else if (Math.abs(cents) <= 5) {
    meterEl.classList.remove("is-idle");
    meterEl.classList.add("is-in-tune");
  } else {
    meterEl.classList.remove("is-idle");
    meterEl.classList.remove("is-in-tune");
  }
}

function updateDisplay(freq, cents) {
  if (freq === null) {
    noteEl.textContent = "\u2013";
    hzEl.textContent = "\u00a0";
    statusEl.textContent = "Play a string";
    return;
  }
  const note = noteFor(freq, a4);
  const nameSpan = note.name;
  const oct = note.octave;
  // Create a sub element for the octave to match design spec
  let sub = noteEl.querySelector("sub");
  if (!sub) {
    sub = document.createElement("sub");
    noteEl.appendChild(sub);
  }
  noteEl.childNodes[0].textContent = nameSpan;
  sub.textContent = oct;
  hzEl.textContent = freq.toFixed(1);
  setMeter(cents);

  // Highlight nearest string
  const btns = tuner?.querySelectorAll('[data-freq]') || [];
  const idx = nearestString(freq);
  btns.forEach((btn, i) => {
    btn.setAttribute("aria-pressed", i === idx ? "true" : "false");
  });
}

function detectLoop(timestamp) {
  rafId = requestAnimationFrame(detectLoop);
  const interval = 1000 / MAX_FPS;
  if (timestamp - lastTime < interval) return;
  lastTime = timestamp;
  if (!analyser) return;
  const buf = new Float32Array(analyser.fftSize);
  analyser.getFloatTimeDomainData(buf);
  const raw = detectPitch(buf, audioCtx.sampleRate);
  const freq = smoothPitch(raw);
  const cents = raw === null ? null : noteFor(raw, a4).cents;
  updateDisplay(freq, cents);
}

function stopMic() {
  if (rafId) {
    cancelAnimationFrame(rafId);
    rafId = null;
  }
  if (micStream) {
    micStream.getTracks().forEach((t) => t.stop());
    micStream = null;
  }
  if (audioCtx) {
    audioCtx.close();
    audioCtx = null;
  }
  analyser = null;
  pitchHistory = [];
  setMeter(null);
  if (noteEl) noteEl.textContent = "\u2013";
  if (hzEl) hzEl.textContent = "\u00a0";
  if (statusEl) statusEl.textContent = "Play a string";
  if (toggleBtn) {
    toggleBtn.querySelector("span").textContent = "Start tuner";
  }
}

async function startMic() {
  try {
    micStream = await navigator.mediaDevices.getUserMedia({
      audio: {
        echoCancellation: false,
        noiseSuppression: false,
        autoGainControl: false,
      },
    });
    audioCtx = new AudioContext();
    const source = audioCtx.createMediaStreamSource(micStream);
    analyser = audioCtx.createAnalyser();
    analyser.fftSize = 4096;
    source.connect(analyser);
    lastTime = 0;
    rafId = requestAnimationFrame(detectLoop);
    if (toggleBtn) {
      toggleBtn.querySelector("span").textContent = "Stop tuner";
    }
    statusEl.textContent = "Listening…";
  } catch {
    if (statusEl) statusEl.textContent = "Mic denied";
  }
}

toggleBtn?.addEventListener("click", () => {
  if (audioCtx && audioCtx.state !== "closed") {
    stopMic();
  } else {
    startMic();
  }
});

// Reference tone playback
tuner?.querySelectorAll('[data-freq]').forEach((btn) => {
  btn.addEventListener("click", () => {
    if (playingOsc) {
      stopTone();
      return;
    }
    const freq = Number(btn.dataset.freq);
    playTone(freq);
  });
});

function playTone(freq) {
  if (!audioCtx || audioCtx.state === "closed") {
    audioCtx = new AudioContext();
  }
  const osc = audioCtx.createOscillator();
  const gain = audioCtx.createGain();
  osc.type = "sine";
  osc.frequency.setValueAtTime(freq, audioCtx.currentTime);
  // 50 ms fade in
  gain.gain.setValueAtTime(0, audioCtx.currentTime);
  gain.gain.linearRampToValueAtTime(0.4, audioCtx.currentTime + 0.05);
  // 50 ms fade out at 2 s
  gain.gain.setValueAtTime(0.4, audioCtx.currentTime + 1.95);
  gain.gain.linearRampToValueAtTime(0, audioCtx.currentTime + 2.0);
  osc.connect(gain);
  gain.connect(audioCtx.destination);
  osc.start();
  osc.stop(audioCtx.currentTime + 2.0);
  playingOsc = osc;
  osc.onended = () => {
    playingOsc = null;
  };
  statusEl.textContent = `Tone: ${freq} Hz`;
}

function stopTone() {
  if (playingOsc) {
    try {
      playingOsc.stop();
    } catch {
      // already stopped
    }
    playingOsc = null;
  }
  statusEl.textContent = "Play a string";
}

// Stop mic on tab hide
document.addEventListener("visibilitychange", () => {
  if (document.hidden) {
    stopMic();
  }
});
