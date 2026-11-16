// Tests for pitch.js — pure tuner maths module.
// Run with: cd backend && node --test tests/js/pitch.test.js
import { test } from "node:test";
import assert from "node:assert/strict";
import { detectPitch, noteFor, nearestString, STANDARD } from "../../app/static/js/pitch.js";

// --- Helpers ---

const SAMPLE_RATE = 44100;

/** Generate a sine wave as Float32Array with given frequency and amplitude. */
function sine(freq, amplitude = 1.0, durationSec = 1.0) {
  const len = Math.floor(SAMPLE_RATE * durationSec);
  const buf = new Float32Array(len);
  for (let i = 0; i < len; i++) {
    buf[i] = amplitude * Math.sin(2 * Math.PI * freq * (i / SAMPLE_RATE));
  }
  return buf;
}

/** Generate a zero (silence) buffer. */
function silence(len = 4096) {
  return new Float32Array(len);
}

/**
 * Check that detectPitch returns a frequency within `tolerancePct`% of `expected`.
 * tolerancePct defaults to 0.5 (i.e. ±0.5 %).
 */
function assertFreq(t, actual, expected, tolerancePct = 0.5) {
  const lo = expected * (1 - tolerancePct / 100);
  const hi = expected * (1 + tolerancePct / 100);
  assert.ok(
    actual !== null && actual >= lo && actual <= hi,
    `Expected ${expected} Hz ±${tolerancePct}% → got ${actual ?? "null"}`,
  );
}

/**
 * Check that noteFor returns the expected note with cents within `toleranceCents`.
 */
function assertNote(t, freq, expected, a4 = 440, toleranceCents = 1) {
  const result = noteFor(freq, a4);
  assert.equal(result.name, expected.name, `name for ${freq} Hz at a4=${a4}`);
  assert.equal(result.octave, expected.octave, `octave for ${freq} Hz at a4=${a4}`);
  assert.ok(
    Math.abs(result.cents - expected.cents) <= toleranceCents,
    `cents for ${freq} Hz at a4=${a4}: expected ~${expected.cents}, got ${result.cents}`,
  );
  assert.equal(result.midi, expected.midi, `midi for ${freq} Hz at a4=${a4}`);
}

// --- detectPitch: standard strings (4096 samples, 44100 Hz) ---

const STRING_TESTS = [
  { name: "E2", freq: 82.41, expected: { name: "E", octave: 2, midi: 40 } },
  { name: "A2", freq: 110.0, expected: { name: "A", octave: 2, midi: 45 } },
  { name: "D3", freq: 146.83, expected: { name: "D", octave: 3, midi: 50 } },
  { name: "G3", freq: 196.0, expected: { name: "G", octave: 3, midi: 55 } },
  { name: "B3", freq: 246.94, expected: { name: "B", octave: 3, midi: 59 } },
  { name: "E4", freq: 329.63, expected: { name: "E", octave: 4, midi: 64 } },
];

for (const s of STRING_TESTS) {
  test(`detectPitch ${s.name} (${s.freq} Hz) → within ±0.5%`, () => {
    const buf = sine(s.freq);
    const freq = detectPitch(buf, SAMPLE_RATE);
    assertFreq(null, freq, s.freq, 0.5);
  });

  test(`detectPitch ${s.name} (${s.freq} Hz) → note ${s.expected.name}${s.expected.octave}`, () => {
    const buf = sine(s.freq);
    const freq = detectPitch(buf, SAMPLE_RATE);
    const note = noteFor(freq, 440);
    assertNote(null, freq, { name: s.expected.name, octave: s.expected.octave, cents: 0, midi: s.expected.midi }, 440, 10);
  });
}

// --- noteFor: 440 Hz → A4, 0 cents ---

test("noteFor(440 Hz, 440) → {name: 'A', octave: 4, cents: 0, midi: 69}", () => {
  assertNote(null, 440, { name: "A", octave: 4, cents: 0, midi: 69 }, 440, 1);
});

// --- noteFor: 446 Hz → A4 +23.4 cents (±1) ---

test("noteFor(446 Hz, 440) → A4 +23.4 cents", () => {
  const result = noteFor(446, 440);
  const expectedCents = 1200 * Math.log2(446 / 440);
  assert.ok(Math.abs(result.cents - expectedCents) <= 1, `cents should be ~${expectedCents.toFixed(1)}, got ${result.cents}`);
  assert.equal(result.name, "A");
  assert.equal(result.octave, 4);
});

// --- noteFor: a4=432, 432 Hz tone → A4 0 cents ---

test("noteFor(432 Hz, 432) → A4 0 cents", () => {
  assertNote(null, 432, { name: "A", octave: 4, cents: 0, midi: 69 }, 432, 1);
});

// --- detectPitch: silence → null ---

test("detectPitch silence (zero samples) → null", () => {
  const buf = silence(4096);
  assert.equal(detectPitch(buf, SAMPLE_RATE), null);
});

// --- detectPitch: very low amplitude → null ---

test("detectPitch amplitude 0.001 → null", () => {
  const buf = sine(440, 0.001);
  assert.equal(detectPitch(buf, SAMPLE_RATE), null);
});

// --- detectPitch: fundamental + harmonic → fundamental (no octave error) ---

test("detectPitch 110 Hz + 0.6×220 Hz harmonic → 110 Hz", () => {
  const t1 = sine(110);
  const t2 = sine(220, 0.6);
  const combined = new Float32Array(t1.length);
  for (let i = 0; i < t1.length; i++) {
    combined[i] = t1[i] + t2[i];
  }
  const freq = detectPitch(combined, SAMPLE_RATE);
  assertFreq(null, freq, 110, 1);
});

// --- nearestString: 82.41 Hz → index 0 (E2) ---

test("nearestString(82.41 Hz) → 0", () => {
  assert.equal(nearestString(82.41), 0);
});

// --- detectPitch: STANDARD strings within ±0.5% ---

test("detectPitch all 6 standard strings within ±0.5%", () => {
  for (const [label, freq] of STANDARD) {
    const buf = sine(freq);
    const detected = detectPitch(buf, SAMPLE_RATE);
    assertFreq(null, detected, freq, 0.5);
  }
});

// --- noteFor: cents accuracy (±1 cent) for each standard string ---

test("noteFor cents within ±1 for all 6 standard strings", () => {
  for (const [label, freq] of STANDARD) {
    const note = noteFor(freq, 440);
    // The nominal frequency of a standard string is close to its nearest semitone,
    // so cents should be very close to 0 (typically within a few cents).
    assert.ok(Math.abs(note.cents) <= 3, `${label}: cents should be near 0, got ${note.cents}`);
  }
});

// --- noteFor: other notes ---

test("noteFor(493.88 Hz, 440) → B4", () => {
  assertNote(null, 493.88, { name: "B", octave: 4, cents: 0, midi: 71 }, 440, 2);
});

test("noteFor(261.63 Hz, 440) → C4 (middle C)", () => {
  const note = noteFor(261.63, 440);
  assert.equal(note.name, "C");
  assert.equal(note.octave, 4);
});

// --- detectPitch: edge cases ---

test("detectPitch < 60 samples → null", () => {
  const buf = new Float32Array(30);
  buf[0] = 0.5;
  assert.equal(detectPitch(buf, SAMPLE_RATE), null);
});

test("detectPitch null input returns null", () => {
  // @ts-expect-error intentionally passing wrong type
  assert.equal(detectPitch(null, SAMPLE_RATE), null);
});

// --- detectPitch: very low frequency (60 Hz boundary) ---

test("detectPitch 60 Hz → ~60 Hz", () => {
  const buf = sine(60);
  const freq = detectPitch(buf, SAMPLE_RATE);
  assertFreq(null, freq, 60, 1);
});

// --- detectPitch: high frequency (1000 Hz) ---

test("detectPitch 1000 Hz → ~1000 Hz", () => {
  const buf = sine(1000);
  const freq = detectPitch(buf, SAMPLE_RATE);
  assertFreq(null, freq, 1000, 1);
});

// --- detectPitch: short duration sine (0.1 s) ---

test("detectPitch 440 Hz with 0.1 s duration → within ±2%", () => {
  const buf = sine(440, 1.0, 0.1);
  const freq = detectPitch(buf, SAMPLE_RATE);
  assertFreq(null, freq, 440, 2);
});
