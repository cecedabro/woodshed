// Tests for metronome.js — pure scheduling module.
// Run with: cd backend && node --test tests/js/metronome.test.js
import { test } from "node:test";
import assert from "node:assert/strict";
import { clampBpm, beatTimes, tapTempo } from "../../app/static/js/metronome.js";

// --- clampBpm ---

test("clampBpm rounds down", () => {
  assert.equal(clampBpm(60.4), 60);
});

test("clampBpm rounds up", () => {
  assert.equal(clampBpm(60.6), 61);
});

test("clampBpm 10 clamps to 20", () => {
  assert.equal(clampBpm(10), 20);
});

test("clampBpm 19.4 clamps to 20", () => {
  assert.equal(clampBpm(19.4), 20);
});

test("clampBpm 20 passes through", () => {
  assert.equal(clampBpm(20), 20);
});

test("clampBpm 400 passes through", () => {
  assert.equal(clampBpm(400), 400);
});

test("clampBpm 999 clamps to 400", () => {
  assert.equal(clampBpm(999), 400);
});

test("clampBpm negative clamps to 20", () => {
  assert.equal(clampBpm(-50), 20);
});

// --- beatTimes ---

test("120 BPM beats at 0.5 s spacing", () => {
  const beats = beatTimes(0, 120, 4, 0, 2000);
  assert.equal(beats.length, 4);
  assert.equal(beats[0].time, 0);
  assert.equal(beats[1].time, 500);
  assert.equal(beats[2].time, 1000);
  assert.equal(beats[3].time, 1500);
});

test("beatsPerBar 4 — accent on beat 1, 5, 9", () => {
  const beats = beatTimes(0, 120, 4, 0, 2000);
  assert.equal(beats[0].beat, 0);
  assert.equal(beats[0].accent, true);
  assert.equal(beats[1].beat, 1);
  assert.equal(beats[1].accent, false);
  assert.equal(beats[2].beat, 2);
  assert.equal(beats[2].accent, false);
  assert.equal(beats[3].beat, 3);
  assert.equal(beats[3].accent, false);
});

test("beatsPerBar 3 — accent on beats 0 and 3", () => {
  const beats = beatTimes(0, 60, 3, 0, 4000);
  assert.equal(beats.length, 4);
  assert.equal(beats[0].accent, true);
  assert.equal(beats[1].accent, false);
  assert.equal(beats[2].accent, false);
  assert.equal(beats[3].accent, true);
});

test("fromBeat skips earlier beats", () => {
  const beats = beatTimes(0, 120, 4, 6, 5000);
  assert.equal(beats.length, 4);
  assert.equal(beats[0].beat, 6);
  assert.equal(beats[0].time, 3000);
});

test("fromBeat 0 — first beat is accented", () => {
  const beats = beatTimes(0, 120, 4, 0, 3000);
  assert.equal(beats[0].accent, true);
  assert.equal(beats[0].beat, 0);
});

test("untilTime is exclusive", () => {
  const beats = beatTimes(0, 120, 4, 0, 1000);
  assert.equal(beats.length, 2);
  assert.equal(beats[0].time, 0);
  assert.equal(beats[1].time, 500);
});

test("untilTime cuts beat at boundary", () => {
  const beats = beatTimes(0, 60, 4, 0, 2000);
  assert.equal(beats.length, 2);
  assert.equal(beats[0].time, 0);
  assert.equal(beats[1].time, 1000);
  // next beat at 2000 is excluded
});

test("beatTimes returns empty when startTime >= untilTime", () => {
  const beats = beatTimes(1000, 120, 4, 0, 1000);
  assert.equal(beats.length, 0);
});

test("beatTimes with fromBeat past untilTime returns empty", () => {
  const beats = beatTimes(0, 120, 4, 20, 1000);
  assert.equal(beats.length, 0);
});

// --- tapTempo ---

test("taps at 500 ms intervals gives 120 bpm", () => {
  const bpm = tapTempo([0, 500, 1000, 1500]);
  assert.equal(bpm, 120);
});

test("fewer than 2 taps returns null", () => {
  assert.equal(tapTempo([]), null);
  assert.equal(tapTempo([500]), null);
});

test("exactly 2 taps gives bpm", () => {
  const bpm = tapTempo([0, 1000]);
  assert.equal(bpm, 60);
});

test("3 taps gives bpm", () => {
  const bpm = tapTempo([0, 500, 1000]);
  assert.equal(bpm, 120);
});

test("a 2.5 s gap restarts the sequence", () => {
  // First 3 taps at 500ms, then a 2500ms gap, then 1 tap
  // After restart: only 1 tap in the new sequence → null
  const bpm = tapTempo([0, 500, 1000, 3500]);
  assert.equal(bpm, null);
});

test("a 2.5 s gap restarts — enough taps after gap", () => {
  // First 2 taps, gap, then 4 taps: only last 4 count
  const bpm = tapTempo([0, 500, 4000, 4500, 5000, 5500, 6000]);
  assert.equal(bpm, 120);
});

test("gap exactly 2000 ms does NOT restart", () => {
  // Taps at 0, 500, 1000, 1500, 2000, 2500, 3000, 3500, 4000
  // All gaps are 500ms, last 4 → 120 bpm
  const bpm = tapTempo([0, 500, 1000, 1500, 2000, 2500, 3000, 3500, 4000]);
  assert.equal(bpm, 120);
});

test("multiple gaps — only last sequence counts", () => {
  // First sequence: 0, 500, 1000 (3 taps → 120bpm)
  // Gap: 3000ms → restart
  // Second sequence: 4500, 5000, 5500, 6000 → 120bpm
  const bpm = tapTempo([0, 500, 1000, 4500, 5000, 5500, 6000]);
  assert.equal(bpm, 120);
});
